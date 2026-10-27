"""HLS (m3u8) video akışı indirici.

* Ana liste (master) → kalite seçenekleri (çözünürlük / bit hızı), ayrı ses kanalı varsa o da.
* Medya listesindeki parçalar (.ts / fMP4) N bağlantıyla paralel indirilir.
* AES-128 şifreli akışlar çözülür (cryptography paketi). DRM'li (SAMPLE-AES) akışlar desteklenmez.
* Biten parçalar kaydedilir → program kapansa bile kaldığı yerden devam eder.
* Sonunda parçalar birleştirilir; ffmpeg varsa .mp4'e dönüştürülür (ses+görüntü birleştirilir).
"""
import os
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.parse

from .appinfo import bundled_ffmpeg
from .engine import CHUNK, MAX_RETRIES, _err_text, _open, scoped_headers
from .i18n import _t

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:
    Cipher = None

HLS_TYPES = ("application/vnd.apple.mpegurl", "application/x-mpegurl",
             "audio/mpegurl", "audio/x-mpegurl")


def is_hls(url, content_type=None):
    return (".m3u8" in urllib.parse.urlparse(url).path.lower()
            or (content_type or "").lower() in HLS_TYPES)


def find_ffmpeg(custom=None):
    """Sıra: ayarlardaki yol → programla birlikte gelen ffmpeg → PATH."""
    if custom and os.path.isfile(custom):
        return custom
    return bundled_ffmpeg() or shutil.which("ffmpeg")


def fetch(url, headers=None, rng=None, origin=None):
    """origin: başlıkların (çerezin) alındığı adres; başka siteye çerez gönderilmez."""
    start, end = rng if rng else (None, None)
    with _open(url, scoped_headers(headers, origin, url), start, end) as r:
        return r.read(), r.geturl()


def _attrs(s):
    return {m.group(1): m.group(2).strip('"')
            for m in re.finditer(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', s)}


def _lines(text):
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def parse_master(text, base):
    lines = _lines(text)
    audio, variants = {}, []
    for i, ln in enumerate(lines):
        if ln.startswith("#EXT-X-MEDIA:"):
            a = _attrs(ln[13:])
            if a.get("TYPE") == "AUDIO" and a.get("URI"):
                g = a.get("GROUP-ID")
                if g not in audio or a.get("DEFAULT") == "YES":
                    audio[g] = urllib.parse.urljoin(base, a["URI"])
        elif ln.startswith("#EXT-X-STREAM-INF:"):
            a = _attrs(ln[18:])
            j = i + 1
            while j < len(lines) and lines[j].startswith("#"):
                j += 1
            if j < len(lines):
                variants.append({"url": urllib.parse.urljoin(base, lines[j]),
                                 "bandwidth": int(a.get("BANDWIDTH") or 0),
                                 "resolution": a.get("RESOLUTION", ""),
                                 "group": a.get("AUDIO")})
    for v in variants:
        v["audio_url"] = audio.get(v.pop("group"))
    # aynı adresi tekrar eden (yedek) varyantları ayıkla
    seen, uniq = set(), []
    for v in sorted(variants, key=lambda v: v["bandwidth"], reverse=True):
        if v["url"] not in seen:
            seen.add(v["url"])
            uniq.append(v)
    return uniq


def parse_media(text, base):
    segs, key, init, endlist = [], None, None, False
    seq, dur, br, last_end = 0, 0.0, None, {}
    for ln in _lines(text):
        if ln.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            seq = int(ln.split(":", 1)[1])
        elif ln.startswith("#EXT-X-KEY:"):
            a = _attrs(ln[11:])
            m = a.get("METHOD", "NONE")
            key = None if m == "NONE" else {"method": m, "uri": urllib.parse.urljoin(base, a.get("URI", "")),
                                            "iv": a.get("IV")}
        elif ln.startswith("#EXT-X-MAP:"):
            a = _attrs(ln[11:])
            rng = None
            if a.get("BYTERANGE"):
                n, _, o = a["BYTERANGE"].partition("@")
                rng = (int(o or 0), int(o or 0) + int(n) - 1)
            init = {"url": urllib.parse.urljoin(base, a["URI"]), "range": rng}
        elif ln.startswith("#EXTINF:"):
            dur = float(ln[8:].split(",")[0] or 0)
        elif ln.startswith("#EXT-X-BYTERANGE:"):
            n, _, o = ln[17:].partition("@")
            br = (int(n), int(o) if o else None)
        elif ln.startswith("#EXT-X-ENDLIST"):
            endlist = True
        elif not ln.startswith("#"):
            url = urllib.parse.urljoin(base, ln)
            rng = None
            if br:
                n, o = br
                o = last_end.get(url, 0) if o is None else o
                rng, last_end[url], br = (o, o + n - 1), o + n, None
            segs.append({"url": url, "dur": dur, "key": key, "seq": seq, "range": rng})
            seq += 1
    return {"segments": segs, "init": init, "endlist": endlist,
            "duration": sum(s["dur"] for s in segs)}


def inspect(url, headers=None):
    """Kalite seçeneklerini döndürür: {"variants": [...], "duration": saniye|None}"""
    data, final = fetch(url, headers)
    text = data.decode("utf-8", "replace")
    if "#EXTM3U" not in text[:2048]:
        raise ValueError(_t("Geçerli bir HLS (m3u8) listesi değil"))
    if "#EXT-X-STREAM-INF" in text:
        return {"variants": parse_master(text, final), "duration": None}
    m = parse_media(text, final)
    return {"variants": [{"url": final, "bandwidth": 0, "resolution": "", "audio_url": None}],
            "duration": m["duration"] if m["endlist"] else None, "live": not m["endlist"]}


def variant_label(v):
    parts = []
    if v.get("resolution"):
        parts.append(v["resolution"])
    if v.get("bandwidth"):
        parts.append(f"{v['bandwidth'] // 1000} kbps")
    if v.get("audio_url"):
        parts.append(_t("ayrı ses"))
    return " · ".join(parts) or _t("Varsayılan")


def _unique(path):
    base, ext = os.path.splitext(path)
    n, p = 1, path
    while os.path.exists(p):
        p = f"{base} ({n}){ext}"
        n += 1
    return p


class HlsTask:
    """HttpTask ile aynı arayüz: start/stop/state/error/downloaded/bar_data/connections_snapshot.

    item.extra: media_url, audio_url, done (["v:12", ...]), bytes, total
    """

    def __init__(self, item, limiter, ffmpeg=None):
        self.item, self.limiter, self.ffmpeg = item, limiter, ffmpeg
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.state, self.error, self.note = "connecting", None, None
        self.conn_info, self.inflight = {}, {}
        self.jobs, self.todo, self.keys = [], [], {}
        ex = item.extra
        self.done = set(ex.setdefault("done", []))
        self.bytes_done = ex.get("bytes", 0)

    @property
    def parts_dir(self):
        return self.item.path + ".tdm_parts"

    # ------------------------------------------------------------ dış API
    def start(self):
        self._run_thread = threading.Thread(target=self._run, daemon=True)
        self._run_thread.start()

    @property
    def alive(self):
        return bool(getattr(self, "_run_thread", None) and self._run_thread.is_alive())

    def join(self, timeout=None):
        if getattr(self, "_run_thread", None):
            self._run_thread.join(timeout)
        return not self.alive

    def stop(self):
        self.stop_event.set()

    def downloaded(self):
        with self.lock:
            return self.bytes_done + sum(self.inflight.values())

    def estimated_size(self):
        with self.lock:
            n = len(self.done)
            return int(self.bytes_done / n * len(self.jobs)) if n and self.jobs else None

    def bar_data(self):
        with self.lock:
            total = len(self.jobs)
            runs, start = [], None
            for i, (name, idx, _) in enumerate(self.jobs):
                ok = f"{name}:{idx}" in self.done
                if ok and start is None:
                    start = i
                if not ok and start is not None:
                    runs.append([start, i - 1, i])
                    start = None
            if start is not None:
                runs.append([start, total - 1, total])
            return total, runs

    def connections_snapshot(self):
        with self.lock:
            return [(n + 1, self.inflight.get(k, 0), None, info)
                    for n, (k, info) in enumerate(sorted(self.conn_info.items()))]

    # ------------------------------------------------------------ iç işleyiş
    def _run(self):
        it, ex = self.item, self.item.extra
        try:
            if any(ex.get(k) and ex[k].lower().endswith(".mpd") for k in ("media_url",)):
                raise ValueError(_t("DASH (.mpd) akışları desteklenmiyor"))
            tracks = [("v", ex["media_url"])]
            if ex.get("audio_url"):
                tracks.append(("a", ex["audio_url"]))
            self.inits, self.counts = {}, {}
            jobs = []
            for name, url in tracks:
                data, final = fetch(url, it.headers, origin=it.url)
                text = data.decode("utf-8", "replace")
                if "#EXT-X-STREAM-INF" in text:  # ana liste verilmiş → en iyi kaliteyi seç
                    v = parse_master(text, final)[0]
                    ex["media_url"] = v["url"]
                    if v.get("audio_url") and not ex.get("audio_url"):
                        ex["audio_url"] = v["audio_url"]
                        tracks.append(("a", v["audio_url"]))
                    data, final = fetch(v["url"], it.headers, origin=it.url)
                    text = data.decode("utf-8", "replace")
                m = parse_media(text, final)
                if not m["endlist"]:
                    raise ValueError(_t("Canlı yayınlar desteklenmiyor (liste bitmemiş)"))
                for s in m["segments"]:
                    if s["key"] and s["key"]["method"] != "AES-128":
                        raise ValueError(_t("Bu video DRM (SAMPLE-AES) ile korunuyor, indirilemez"))
                    if s["key"] and Cipher is None:
                        raise ValueError(_t("Şifreli akış: 'pip install cryptography' gerekli"))
                self.inits[name] = m["init"]
                self.counts[name] = len(m["segments"])
                jobs += [(name, i, s) for i, s in enumerate(m["segments"])]
            if not jobs:
                raise ValueError(_t("Listede hiç parça yok"))
            with self.lock:
                self.jobs = jobs
                self.todo = [j for j in jobs if f"{j[0]}:{j[1]}" not in self.done]
            ex["total"] = len(jobs)
            os.makedirs(self.parts_dir, exist_ok=True)
            self.state = "downloading"

            workers = [threading.Thread(target=self._worker, daemon=True)
                       for _ in range(max(1, it.connections))]
            for t in workers:
                t.start()
            for t in workers:
                t.join()
            if self.state == "error":
                return
            if self.stop_event.is_set():
                self.state = "stopped"
                return
            self._assemble()
            self.state = "completed"
        except Exception as e:  # noqa: BLE001
            if self.stop_event.is_set() and self.state != "error":
                self.state = "stopped"
            else:
                self.error, self.state = _err_text(e), "error"

    def _worker(self):
        while not self.stop_event.is_set():
            with self.lock:
                if not self.todo:
                    return
                job = self.todo.pop(0)
            if not self._get_segment(job):
                with self.lock:
                    self.todo.insert(0, job)
                return

    def _get_segment(self, job):
        name, idx, s = job
        key = f"{name}:{idx}"
        try:
            for attempt in range(MAX_RETRIES + 1):
                if self.stop_event.is_set():
                    return False
                self.conn_info[key] = _t("{0} parçası {1}").format(_t('Ses') if name == 'a' else _t('Görüntü'), idx + 1)
                try:
                    buf = bytearray()
                    with _open(s["url"], scoped_headers(self.item.headers, self.item.url, s["url"]),
                               *(s["range"] or (None, None))) as r:
                        while True:
                            chunk = r.read(CHUNK)
                            if not chunk:
                                break
                            if self.stop_event.is_set():
                                return False
                            self.limiter.consume(len(chunk))
                            buf += chunk
                            with self.lock:
                                self.inflight[key] = len(buf)
                    data = self._decrypt(bytes(buf), s) if s["key"] else bytes(buf)
                    p = os.path.join(self.parts_dir, f"{name}{idx:06d}")
                    with open(p + ".tmp", "wb") as f:
                        f.write(data)
                    os.replace(p + ".tmp", p)
                    with self.lock:
                        self.inflight.pop(key, None)
                        self.bytes_done += len(buf)
                        self.done.add(key)
                        self.item.extra["done"].append(key)
                        self.item.extra["bytes"] = self.bytes_done
                    return True
                except Exception as e:  # noqa: BLE001
                    with self.lock:
                        self.inflight.pop(key, None)
                    if self.stop_event.is_set():
                        return False
                    fatal = isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 404, 410)
                    if fatal or attempt == MAX_RETRIES:
                        self._fail(e)
                        return False
                    self.conn_info[key] = _t("Hata, yeniden deneniyor ({0}/{1})").format(attempt + 1, MAX_RETRIES)
                    self.stop_event.wait(min(2 ** (attempt + 1), 30))
            return False
        finally:
            self.conn_info.pop(key, None)

    def _key(self, uri):
        with self.lock:
            if uri in self.keys:
                return self.keys[uri]
        data, _ = fetch(uri, self.item.headers, origin=self.item.url)
        with self.lock:
            self.keys[uri] = data
        return data

    def _decrypt(self, data, s):
        k = s["key"]
        if k["iv"]:
            h = k["iv"][2:] if k["iv"].lower().startswith("0x") else k["iv"]
            iv = bytes.fromhex(h.rjust(32, "0"))
        else:
            iv = s["seq"].to_bytes(16, "big")
        d = Cipher(algorithms.AES(self._key(k["uri"])), modes.CBC(iv)).decryptor()
        out = d.update(data) + d.finalize()
        pad = out[-1] if out else 0
        if 1 <= pad <= 16 and out.endswith(bytes([pad]) * pad):
            out = out[:-pad]
        return out

    def _assemble(self):
        it = self.item
        self.conn_info = {"z": _t("Parçalar birleştiriliyor…")}
        outs = {}
        for name, count in self.counts.items():
            if self.inits.get(name):
                ext = ".mp4" if name == "v" else ".m4a"
            else:
                first = next(s for n, _, s in self.jobs if n == name)
                ext = os.path.splitext(urllib.parse.urlparse(first["url"]).path)[1].lower()
                ext = ext if ext in (".ts", ".aac", ".mp3", ".ac3") else ".ts"
            out = os.path.join(self.parts_dir, f"track_{name}{ext}")
            with open(out, "wb") as f:
                init = self.inits.get(name)
                if init:
                    f.write(fetch(init["url"], it.headers, init["range"], origin=it.url)[0])
                for i in range(count):
                    with open(os.path.join(self.parts_dir, f"{name}{i:06d}"), "rb") as src:
                        shutil.copyfileobj(src, f, 1 << 20)
            outs[name] = out

        base, ext = os.path.splitext(it.path)
        ff = self.ffmpeg
        final = None
        if ff and ext.lower() in (".mp4", ".mkv", ".mov", ".m4v"):
            target = _unique(it.path)
            probe = ["-probesize", "100M", "-analyzeduration", "100M"]  # akış parametrelerini tam algıla
            args = [ff, "-y", "-loglevel", "error", *probe, "-i", outs["v"]]
            if "a" in outs:
                args += [*probe, "-i", outs["a"], "-map", "0:v:0?", "-map", "1:a:0"]
            args += ["-c", "copy", target]
            self.conn_info = {"z": _t("ffmpeg ile dönüştürülüyor…")}
            r = subprocess.run(args, capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode == 0 and os.path.exists(target):
                final = target
            else:
                self.note = _t("ffmpeg dönüştüremedi: ") + r.stderr.decode("utf-8", "replace")[-200:]
                if os.path.exists(target):
                    os.remove(target)
        if not final:
            vext = os.path.splitext(outs["v"])[1]
            if "a" in outs:
                final = _unique(base + vext)
                shutil.move(outs["a"], _unique(base + ".ses" + os.path.splitext(outs["a"])[1]))
                why = _t("ffmpeg birleştiremediği") if self.note else _t("ffmpeg olmadığı")
                self.note = ((self.note or "") + _t(" {0} için ses ayrı dosyaya kaydedildi.").format(why)).strip()
            else:
                final = _unique(base + vext)
            shutil.move(outs["v"], final)
        shutil.rmtree(self.parts_dir, ignore_errors=True)
        it.path = final
        it.size = os.path.getsize(final)
        self.bytes_done = it.size
        self.conn_info = {}

    def _fail(self, e):
        self.error, self.state = _err_text(e), "error"
        self.stop_event.set()
