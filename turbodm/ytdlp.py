"""Site videoları (YouTube vb.) — yt-dlp ile.

* yt-dlp.exe ve deno.exe (YouTube'un JavaScript şifresini çözen, dosya/ağ erişimi kapalı JS motoru)
  programla birlikte gelir: {kurulum}\\tools\\.
* YouTube sık değiştiği için yt-dlp kullanıcının klasörüne (%LOCALAPPDATA%\\TurboDM\\tools) güncellenebilir;
  varsa güncel kopya tercih edilir. Program dosyalarına yazma izni gerekmez.
* Hızlı mod: yt-dlp yalnızca akış adreslerini çözer, indirmeyi TurboDM'in çok bağlantılı motoru yapar
  (görüntü ve ses aynı anda, istek başına ≤10 MB), sonra ffmpeg birleştirir. Uygun değilse (parçalı akış,
  çerez gerektiren site) yt-dlp'nin kendi indiricisi kullanılır; durdurunca .part dosyalarından devam eder.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request

from .appinfo import install_dir
from .engine import SSL_CONTEXT
from .i18n import _t

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
USER_TOOLS = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "TurboDM", "tools")
YT_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")


def is_youtube(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in YT_HOSTS)


def canonical_url(url):
    """Tarayıcıdan gelen sayfa adresini tek videoya indirger (YouTube: oynatma listesi / zaman parametreleri,
    kısa video, gömülü oynatıcı ve youtu.be biçimleri → watch?v=…). Diğer adresler olduğu gibi kalır."""
    if not is_youtube(url):
        return url
    u = urllib.parse.urlparse(url)
    vid = urllib.parse.parse_qs(u.query).get("v", [None])[0]
    m = re.match(r"^/(shorts|live|embed)/([\w-]{6,})", u.path)
    if not vid and m:
        vid = m.group(2)
    if not vid and (u.hostname or "").endswith("youtu.be"):
        vid = u.path.strip("/").split("/")[0] or None
    return f"https://www.youtube.com/watch?v={vid}" if vid else url


def _bundled(*names):
    base = install_dir()
    for sub in ("tools", os.path.join("vendor", "ytdlp"), os.path.join("vendor", "deno")):
        for n in names:
            p = os.path.join(base, sub, n)
            if os.path.isfile(p):
                return p
    return None


def ytdlp_path():
    """Kullanıcı klasöründeki güncellenmiş kopya varsa o, yoksa programla gelen."""
    user = os.path.join(USER_TOOLS, "yt-dlp.exe")
    if os.path.isfile(user):
        return user
    return _bundled("yt-dlp.exe") or shutil.which("yt-dlp")


def deno_path():
    return _bundled("deno.exe") or shutil.which("deno")


def available():
    return ytdlp_path() is not None


def version():
    p = ytdlp_path()
    if not p:
        return None
    try:
        r = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


# yt-dlp.exe bir Python programı: boru (pipe) çıktısını varsayılan olarak Windows ANSI kod sayfasıyla
# (Türkçe Windows'ta cp1254) yazar. "™", Japonca vb. karakterli başlıklar UTF-8 okununca bozulur ve
# dosya yolu bulunamaz. Hem ortam değişkeniyle hem --encoding ile UTF-8'e zorlanır.
UTF8_ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")


def _header_args(url, headers):
    """Gömülü oynatıcılar: video sunucusu isteğin oynatıcı sayfasından geldiğini (Referer/Origin) denetler;
    tarayıcının gönderdiği bu başlıklar yt-dlp'ye de verilir. YouTube'da yt-dlp kendi başlıklarını kullanır."""
    if not headers or is_youtube(url):
        return []
    h = {k.lower(): v for k, v in headers.items() if isinstance(v, str) and v}
    out = []
    if h.get("referer"):
        out += ["--referer", h["referer"]]
    if h.get("origin"):
        out += ["--add-header", "Origin:" + h["origin"]]
    return out


def _base_args(ffmpeg=None, cookies_file=None, url=None, headers=None):
    args = [ytdlp_path(), "--no-warnings", "--no-playlist", "--ignore-config", "--no-color",
            "--encoding", "utf-8"] + _header_args(url, headers)
    deno = deno_path()
    if deno:
        args += ["--js-runtimes", f"deno:{deno}"]
    if ffmpeg:
        args += ["--ffmpeg-location", ffmpeg]
    if cookies_file:
        args += ["--cookies", cookies_file]
    # Seçenekler → Bağlantı: vekil sunucu ve (değiştirildiyse) tarayıcı kimliği video motoruna da geçer
    from . import engine
    proxy = engine.proxy_for_tools()
    if proxy is not None:
        args += ["--proxy", proxy]
    if engine.NET.user_agent.strip():
        args += ["--user-agent", engine.NET.user_agent.strip()]
    return args


def write_cookies(cookies):
    """Tarayıcı eklentisinin gönderdiği çerezleri Netscape biçiminde geçici dosyaya yazar."""
    if not cookies:
        return None
    fd, path = tempfile.mkstemp(prefix="tdm_ck_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            dom = c.get("domain", "")
            f.write("\t".join([
                dom, "TRUE" if dom.startswith(".") else "FALSE", c.get("path", "/"),
                "TRUE" if c.get("secure") else "FALSE", str(int(c.get("expirationDate") or 0)),
                c.get("name", ""), c.get("value", "")]) + "\n")
    return path


MEDIA_EXTS = (".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".opus", ".ogg", ".mov", ".flv", ".aac", ".wav")


def find_output(base, preferred_ext=None):
    """<base>.<uzantı> biçimindeki tamamlanmış çıktı dosyasını bulur (yarım parçaları hariç)."""
    folder, stem = os.path.split(base)
    exts = ([("." + preferred_ext.lstrip("."))] if preferred_ext else []) + list(MEDIA_EXTS)
    for ext in exts:
        p = os.path.join(folder, stem + ext)
        if os.path.isfile(p):
            return p
    return None


_MEDIA_EXT = r"(?:mp4|webm|m4a|mkv|mp3|opus|ogg|aac|flv|3gp|mov|bin)"
_PART_SUFFIX = r"(?:\.part(?:-Frag\d+(?:\.part)?)?|\.ytdl)"
# Yalnızca yt-dlp'nin ve TurboDM'in ürettiği tam ad kalıpları (<ad> = indirmenin adı, uzantısız):
#   <ad>.f137.mp4  <ad>.f251-drc.webm.part  <ad>.f137.mp4.tdm   (biçim etiketli parçalar)
#   <ad>.mp4.part  <ad>.mp4.ytdl  <ad>.mp4.part-Frag3            (yt-dlp ara dosyaları)
#   <ad>.temp.mp4                                                 (birleştirme ara dosyası)
# "Film.2023.1080p.mkv", "Film.final.mp4" ya da bitmiş "Film.mkv" gibi dosyalar ASLA eşleşmez.
_PARTIAL_RE = re.compile(
    rf"\.f\d+(?:-[A-Za-z0-9]+)?\.{_MEDIA_EXT}(?:{_PART_SUFFIX}|\.tdm)?"
    rf"|\.{_MEDIA_EXT}{_PART_SUFFIX}"
    rf"|\.temp\.{_MEDIA_EXT}", re.IGNORECASE)


def partial_files(path):
    """Bu indirmenin yarım bıraktığı ara dosyalar (sıkı eşleşme; bkz. _PARTIAL_RE)."""
    folder, name = os.path.split(path)
    stem = os.path.splitext(name)[0]
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return [os.path.join(folder, n) for n in names
            if n != name and n.startswith(stem + ".") and _PARTIAL_RE.fullmatch(n[len(stem):])]


# ------------------------------------------------------------------ kalite listesi
def inspect(url, ffmpeg=None, cookies=None, headers=None):
    """Video bilgisi ve sunulacak kalite seçenekleri.
    Dönüş: {"title", "duration", "thumbnail", "choices": [{"label", "format", "ext", "size"}]}"""
    ck = write_cookies(cookies)
    try:
        r = subprocess.run(_base_args(ffmpeg, ck, url, headers) + ["-J", url], capture_output=True, timeout=120,
                           env=UTF8_ENV, creationflags=NO_WINDOW)
    finally:
        if ck:
            os.remove(ck)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip().splitlines()
        msg = next((e for e in reversed(err) if "ERROR" in e), err[-1] if err else _t("bilinmeyen hata"))
        raise RuntimeError(_friendly_error(msg))
    info = json.loads(r.stdout.decode("utf-8", "replace"))
    if info.get("_type") == "playlist":
        raise RuntimeError(_t("Bu bir oynatma listesi; tek bir video bağlantısı verin."))
    return {"title": info.get("title") or "video", "duration": info.get("duration"),
            "id": info.get("id"), "extractor": info.get("extractor_key"),
            "choices": build_choices(info.get("formats") or [], info.get("duration"))}


def _size(f, duration):
    s = f.get("filesize") or f.get("filesize_approx")
    if not s and duration and f.get("tbr"):
        s = f["tbr"] * 1000 / 8 * duration
    return int(s) if s else 0


STREAM_KEYS = ("format_id", "url", "http_headers", "filesize", "ext", "vcodec", "acodec", "protocol")


def _streams(formats, fmt):
    """Kalite listesi alınırken gelen akış adresleri: indirme hemen başlarsa yt-dlp'yi (ve YouTube'u)
    ikinci kez çağırmaya gerek kalmaz. Adresler birkaç saat geçerli; yalnızca bellekte tutulur."""
    by_id = {str(f.get("format_id")): f for f in formats}
    out = []
    for fid in str(fmt).split("+"):
        f = by_id.get(fid)
        if not f or f.get("fragments") or f.get("cookies"):
            return None
        out.append({k: f.get(k) for k in STREAM_KEYS})
    return out


def build_choices(formats, duration=None):
    """Video+ses birleşik kalite seçenekleri (H.264 öncelikli: her oynatıcıda açılır) + yalnızca ses."""
    def direct(f):  # doğrudan https (DASH) — HLS kopyalarından hızlı ve küçük
        p = str(f.get("protocol", ""))
        return p.startswith("http") and "m3u8" not in p

    video = [f for f in formats if f.get("vcodec") not in (None, "none") and f.get("height")]
    audio = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")
             and direct(f)]
    # m4a (mp4 içine sorunsuz girer) > normal ses (drc = dinamik aralığı sıkıştırılmış değil) > yüksek bit hızı
    # çok dilli videolarda orijinal ses (language_preference: orijinal 10, dublaj -1, tek ses None)
    best_audio = max(audio, key=lambda f: (f.get("language_preference") or 0, f.get("ext") == "m4a",
                                           "drc" not in str(f.get("format_id", "")), f.get("abr") or 0),
                     default=None)
    choices = []
    for h in sorted({f["height"] for f in video}, reverse=True):
        cands = [f for f in video if f["height"] == h]
        cands = [f for f in cands if direct(f)] or cands
        avc = [f for f in cands if str(f.get("vcodec", "")).startswith("avc1")]
        pick = max(avc or cands, key=lambda f: (f.get("fps") or 0, f.get("tbr") or 0))
        codec = "H.264" if avc else str(pick.get("vcodec", "")).split(".")[0].upper().replace("VP09", "VP9").replace("AV01", "AV1")
        fps = f" {int(pick['fps'])}fps" if (pick.get("fps") or 0) > 30 else ""
        has_audio = pick.get("acodec") not in (None, "none")
        size = _size(pick, duration) + (0 if has_audio or not best_audio else _size(best_audio, duration))
        fmt = pick["format_id"] if has_audio or not best_audio else f"{pick['format_id']}+{best_audio['format_id']}"
        label = _t("{0}p{1} · {2}").format(h, fps, codec) + (_t(" · ≈{0:.0f} MB").format(size / 1048576) if size else "")
        choices.append({"label": label, "format": fmt, "ext": "mp4", "size": size, "height": h,
                        "streams": _streams(formats, fmt)})
    if best_audio:
        size = _size(best_audio, duration)
        choices.append({"label": _t("Yalnızca ses · {0}").format(best_audio.get('ext', 'm4a'))
                                  + (_t(" · ≈{0:.0f} MB").format(size / 1048576) if size else ""),
                        "format": best_audio["format_id"], "ext": best_audio.get("ext", "m4a"),
                        "size": size, "height": 0, "streams": _streams(formats, best_audio["format_id"])})
    if not choices:  # tek dosya sunan siteler
        f = max(formats, key=lambda f: f.get("tbr") or 0, default=None)
        if f:
            choices.append({"label": _t("En iyi kalite"), "format": f["format_id"], "ext": f.get("ext", "mp4"),
                            "size": _size(f, duration), "height": f.get("height") or 0})
    return choices


def _friendly_error(msg):
    m = msg.lower()
    if "sign in to confirm" in m or "not a bot" in m:
        return (_t("YouTube giriş doğrulaması istiyor. Videoyu tarayıcı eklentisindeki düğmeyle gönderin (oturum çerezleri birlikte gönderilir) ya da biraz sonra tekrar deneyin."))
    if "private video" in m:
        return _t("Bu video gizli.")
    if "members-only" in m or "join this channel" in m:
        return _t("Bu video yalnızca kanal üyelerine açık.")
    if "drm" in m:
        return _t("Bu video DRM ile korunuyor, indirilemez.")
    if "unsupported url" in m:
        return _t("Bu adreste indirilebilir bir video bulunamadı.")
    return re.sub(r"^ERROR:\s*(\[[^\]]+\]\s*)?", "", msg).strip()


# ------------------------------------------------------------------ indirme görevi
_PROGRESS = re.compile(r"^TDMP (\S+) (\S+) (\S+) (\S+) (\S+)")

# Hızlı mod (IDM yöntemi): yt-dlp yalnızca gerçek akış adreslerini çözer; indirmeyi TurboDM'in çok
# bağlantılı motoru yapar. YouTube bir isteğin ilk ~10 MB'ından sonrasını kısar → her istek ≤ 10 MB,
# çok sayıda bağlantı. Ölçüm (1 Gbit hat): yt-dlp ~40 MB/s, 24 bağlantı × 10 MB ~99 MB/s.
FAST_MAX_REQUEST = 10 * 1024 * 1024
FAST_VIDEO_CONNECTIONS = 24
FAST_AUDIO_CONNECTIONS = 4
FAST_MAX_REFRESH = 3          # adres süresi dolarsa (HTTP 403/410) yeniden çözme hakkı


class _Part:
    """HttpTask'ın beklediği 'item' arayüzü: tek bir akış (görüntü ya da ses)."""

    def __init__(self, fid, kind, url, headers, path, size, segments, connections):
        self.fid, self.kind = fid, kind
        self.url, self.headers, self.path = url, headers, path
        self.size, self.segments = size, segments
        self.resumable, self.connections = True, connections
        self.max_request = FAST_MAX_REQUEST


class _DoneTask:
    """Önceki çalışmada tamamlanmış parça için HttpTask yerine geçen nesne (aynı arayüz).
    Listede None tutmak duraklat/ilerleme/çıkış yollarında çökmeye yol açıyordu."""
    state, error = "completed", None
    alive = False

    def __init__(self, p):
        self.size = p.size or (os.path.getsize(p.path) if os.path.isfile(p.path) else 0)

    def stop(self):
        pass

    def join(self, timeout=None):
        return True

    def downloaded(self):
        return self.size

    def segments_snapshot(self):
        return [[0, self.size - 1, self.size]] if self.size else []

    def connections_snapshot(self):
        return []


class YtdlpTask:
    """HttpTask ile aynı arayüz (start/stop/state/error/downloaded/bar_data/connections_snapshot).

    item.extra: format, ext, title, cookies (yalnızca bellekte), size,
                parts {format_id: {path, size, segments, done}}  ← hızlı modda devam bilgisi
                native: True  ← hızlı mod bu video için kullanılamıyorsa yt-dlp'nin kendi indiricisi
    """

    def __init__(self, item, limiter=None, ffmpeg=None):
        self.item, self.limiter, self.ffmpeg = item, limiter, ffmpeg
        self.rate = getattr(limiter, "rate", 0) or 0
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.state, self.error, self.note = "connecting", None, None
        self.mode = None         # "fast" | "native"
        self.proc = None
        self.done_formats = {}   # native: format_id -> bayt
        self.cur = (None, 0, 0)  # native: (format_id, indirilen, toplam)
        self.parts = []          # fast: [(_Part, HttpTask)]
        self.phase = _t("Video adresleri çözülüyor…")

    # ---------------------------------------------------------------- dış API
    def start(self):
        self._run_thread = threading.Thread(target=self._run, daemon=True)
        self._run_thread.start()

    @property
    def alive(self):
        # alt görevlerden biri hâlâ yazıyorsa görev bitmiş sayılmaz (yönetici yeni görevi bekletir)
        return bool((getattr(self, "_run_thread", None) and self._run_thread.is_alive())
                    or any(getattr(t, "alive", False) for _, t in list(self.parts)))

    def join(self, timeout=None):
        end = time.time() + (timeout if timeout is not None else 1e9)
        if getattr(self, "_run_thread", None):
            self._run_thread.join(timeout)
        for _, t in list(self.parts):
            t.join(max(0.1, end - time.time()))
        return not self.alive

    def stop(self):
        self.stop_event.set()
        for _, t in list(self.parts):
            t.stop()
        p = self.proc
        if p and p.poll() is None:
            # yt-dlp'yi ve alt süreçlerini (ffmpeg) kapat; .part dosyaları kalır → devam edilebilir
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True,
                           creationflags=NO_WINDOW)

    def downloaded(self):
        if self.mode == "fast":
            return sum(t.downloaded() for _, t in list(self.parts))
        with self.lock:
            fid, got, _ = self.cur
            return sum(v for k, v in self.done_formats.items() if k != fid) + got

    def estimated_size(self):
        if self.mode == "fast":
            total = sum(p.size or 0 for p, _ in list(self.parts))
            return total or self.item.extra.get("size") or None
        with self.lock:
            fid, _, total = self.cur
            known = sum(v for k, v in self.done_formats.items() if k != fid) + total
        return max(known, self.item.extra.get("size") or 0) or None

    def bar_data(self):
        if self.mode == "fast" and self.parts:
            off, segs = 0, []
            for p, t in list(self.parts):
                for a, b, pos in t.segments_snapshot():
                    segs.append([a + off, b + off, pos + off])
                off += p.size or 0
            return (off or 1), segs
        size = self.estimated_size() or 0
        got = self.downloaded()
        return (size or 1), [[0, max(0, (size or 1) - 1), min(got, size or 1)]]

    def connections_snapshot(self):
        if self.mode == "fast":
            out = []
            for p, t in list(self.parts):
                label = _t("Görüntü") if p.kind == "video" else "Ses"
                for _, done, total, info in t.connections_snapshot():
                    out.append((len(out) + 1, done, total, f"{label} · {info}"))
            return out or [(1, 0, None, self.phase)]
        fid, got, total = self.cur
        return [(1, got, total or None, self.phase)]

    # ---------------------------------------------------------------- iş akışı
    def _run(self):
        it, ex = self.item, self.item.extra
        try:
            os.makedirs(os.path.dirname(it.path), exist_ok=True)
            if os.path.isfile(it.path) and os.path.getsize(it.path) > 0 and not ex.get("parts"):
                # Çıktı zaten tamam (ör. önceki sürümde bitmiş ama hata sanılmış indirme): yeniden indirme.
                # Eklerken yol benzersiz seçildiği için bu dosya ancak bu indirmenin çıktısı olabilir.
                it.size = os.path.getsize(it.path)
                self.mode, self.state = "done", "completed"
                return
            if not ex.get("native"):
                fmts = self._resolve()
                if self.stop_event.is_set():
                    self.state = "stopped"
                    return
                if fmts:
                    if self._run_fast(fmts):
                        return
                    # hızlı mod bu videoda olmadı → yt-dlp'nin kendi indiricisiyle devam
                    ex["native"] = True
                    self._discard_fast_parts()
            self._run_native()
        except Exception as e:  # noqa: BLE001
            # son güvence: hiçbir alt görev sahipsiz yazmaya devam etmesin
            self._halt_parts(sync=False)
            if self.stop_event.is_set():
                self.state = "stopped"
            else:
                self.error, self.state = str(e), "error"

    def _resolve(self):
        """Seçilen biçimin doğrudan indirilebilir akış adresleri; uygun değilse None (yedek yol)."""
        ex = self.item.extra
        pre, age = ex.pop("streams", None), time.time() - ex.pop("streams_t", 0)
        if pre and age < 1800 and all(str(f.get("protocol")) in ("http", "https") and f.get("url") for f in pre):
            return pre  # kalite listesinden gelen taze adresler (YouTube'a ikinci istek yok)
        ck = write_cookies(ex.get("cookies"))
        try:
            r = subprocess.run(_base_args(self.ffmpeg, ck, self.item.url, self.item.headers) + ["-J", "-f", ex["format"], self.item.url],
                               capture_output=True, timeout=120, env=UTF8_ENV, creationflags=NO_WINDOW)
        finally:
            if ck and os.path.exists(ck):
                os.remove(ck)
        if r.returncode != 0:
            err = r.stderr.decode("utf-8", "replace").strip().splitlines()
            msg = next((e for e in reversed(err) if "ERROR" in e), err[-1] if err else "")
            raise RuntimeError(_friendly_error(msg) if msg else _t("Video bilgisi alınamadı"))
        info = json.loads(r.stdout.decode("utf-8", "replace"))
        fmts = info.get("requested_formats") or [info]
        for f in fmts:
            proto = str(f.get("protocol", ""))
            # yalnızca doğrudan http(s) dosyalar; parçalı akışlar (m3u8/dash) ve çerez isteyenler yedek yola
            if proto not in ("http", "https") or not f.get("url") or f.get("fragments") or f.get("cookies"):
                return None
        return fmts

    # ---- hızlı mod
    def _make_parts(self, fmts):
        it, ex = self.item, self.item.extra
        out_dir, name = os.path.split(it.path)
        stem = os.path.splitext(name)[0]
        saved = ex.setdefault("parts", {})
        parts = []
        for i, f in enumerate(fmts):
            fid = str(f["format_id"])
            kind = "video" if f.get("vcodec") not in (None, "none") else "audio"
            st = saved.get(fid) or {}
            path = st.get("path") or os.path.join(out_dir, f"{stem}.f{fid}.{f.get('ext') or 'bin'}")
            size = st.get("size") or f.get("filesize")
            conns = FAST_VIDEO_CONNECTIONS if kind == "video" else FAST_AUDIO_CONNECTIONS
            conns = max(conns, int(it.connections or 0)) if kind == "video" else conns
            p = _Part(fid, kind, f["url"], dict(f.get("http_headers") or {}), path, size,
                      [list(s) for s in (st.get("segments") or [])], min(32, conns))
            p.done = bool(st.get("done")) and os.path.isfile(path)
            parts.append(p)
        return parts

    def _sync_extra(self):
        """Devam bilgisini (segmentler) item.extra'ya yaz; manager bunu düzenli kaydeder."""
        saved = {}
        for p, t in list(self.parts):
            saved[p.fid] = {"path": p.path, "size": p.size, "segments": t.segments_snapshot(),
                            "done": t.state == "completed"}
        with self.lock:
            self.item.extra["parts"] = saved

    def _start_part(self, p):
        from .engine import HttpTask  # döngüsel içe aktarmayı önle
        t = HttpTask(p, self.limiter)
        t.start()
        return t

    def _halt_parts(self, sync=True):
        """Tüm alt görevleri durdur ve bağlantıları gerçekten kapanana kadar bekle."""
        for _, t in list(self.parts):
            t.stop()
        self._wait_parts()
        if sync and self.parts:
            self._sync_extra()

    def _run_fast(self, fmts):
        """True: tamamlandı/durduruldu (işlendi). False: yedek yola (yt-dlp) geç. Hata: istisna."""
        self.mode = "fast"
        parts = self._make_parts(fmts)
        self.parts = [(p, _DoneTask(p) if p.done else self._start_part(p)) for p in parts]
        self.phase = _t("İndiriliyor")
        refreshes, mark = 0, self.downloaded()
        while True:
            if self.stop_event.is_set():
                self._halt_parts()
                self.state = "stopped"
                return True
            states = [(p, t, t.state) for p, t in self.parts]
            if any(s == "downloading" for _, _, s in states):
                self.state = "downloading"
            failed = [t for _, t, s in states if s == "error"]
            if failed:
                errs = " ".join(t.error or "" for t in failed)
                expired = any(c in errs for c in ("HTTP 403", "HTTP 410", "HTTP 404"))
                if not expired:
                    self._halt_parts()
                    raise RuntimeError(errs.strip() or _t("İndirme hatası"))
                # Akış adresinin süresi doldu. İlerleme oldukça hak sıfırlanır; ilerleme yokken art arda
                # reddediliyorsa sonsuz döngüye girilmez.
                if self.downloaded() - mark > 16 * 1024 * 1024:
                    refreshes, mark = 0, self.downloaded()
                if refreshes >= FAST_MAX_REFRESH:
                    return self._give_up()
                refreshes += 1
                if not self._refresh_urls():
                    return self._give_up()
                continue
            if all(s == "completed" for _, _, s in states):
                self._sync_extra()
                self._merge([p for p, _ in self.parts])
                return True
            self._sync_extra()
            self.stop_event.wait(0.25)

    def _refresh_urls(self):
        """Tek bir yeniden çözümlemeyle bitmemiş TÜM parçaların adreslerini yenile ve kaldığı yerden sürdür.
        (Aynı anda alınmış adreslerin hepsinin süresi birlikte dolar; yalnızca hata vereni yenilemek
        yenileme hakkını boşa harcıyordu.) False: biçim artık sunulmuyor."""
        self.phase = _t("Adres yenileniyor…")
        # Önce eski bağlantılar tamamen kapanmalı: aynı segmentlere iki görev yazarsa dosyaya boşluk karışır.
        self._halt_parts()
        try:
            fresh = {str(f["format_id"]): f for f in (self._resolve() or [])}
        except Exception:
            self._sync_extra()
            raise
        if self.stop_event.is_set():
            return True  # döngü durdurmayı işler
        new = []
        for p, t in self.parts:
            if t.state != "completed":
                f = fresh.get(p.fid)
                if not f:
                    return False
                p.url, p.headers = f["url"], dict(f.get("http_headers") or {})
                t = self._start_part(p)
            new.append((p, t))
        self.parts = new
        self.phase = _t("İndiriliyor")
        return True

    def _give_up(self):
        """Hızlı mod adres yenilemeye rağmen reddediliyor. Az indirildiyse yt-dlp'nin kendi indiricisine geç
        (False); anlamlı veri indirildiyse silme — kullanıcı daha sonra Devam Et ile kaldığı yerden sürdürür."""
        self._halt_parts()
        total = self.estimated_size() or 0
        if self.downloaded() < max(32 * 1024 * 1024, total * 0.05):
            return False
        raise RuntimeError(_t("YouTube akış adresini şu an kabul etmiyor. İndirilen kısım korundu; biraz sonra Devam Et ile kaldığı yerden sürdürebilirsiniz."))

    def _wait_parts(self, timeout=30):
        """Tüm alt görevlerin bağlantıları gerçekten kapanana kadar bekle."""
        end = time.time() + timeout
        for _, t in list(self.parts):
            t.join(max(0.1, end - time.time()))

    def _merge(self, parts):
        it, ex = self.item, self.item.extra
        base = os.path.splitext(it.path)[0]
        if len(parts) == 1:
            p = parts[0]
            final = _unique(base + os.path.splitext(p.path)[1])
            os.replace(p.path, final)
            leftovers = []
        else:
            self.phase = _t("Birleştiriliyor (ffmpeg)…")
            if not self.ffmpeg:
                raise RuntimeError(_t("Görüntü ve sesi birleştirmek için ffmpeg gerekli"))
            video = next(p for p in parts if p.kind == "video")
            audio = next(p for p in parts if p.kind == "audio")
            ext = "." + (ex.get("ext") or "mp4").lstrip(".")
            final = _unique(base + ext)
            tmp = base + ".temp" + ext
            r = subprocess.run([self.ffmpeg, "-y", "-loglevel", "error", "-i", video.path, "-i", audio.path,
                                "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", tmp],
                               capture_output=True, creationflags=NO_WINDOW)
            if r.returncode != 0 or not os.path.isfile(tmp):
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise RuntimeError(_t("ffmpeg birleştiremedi: ") + r.stderr.decode("utf-8", "replace")[-200:])
            os.replace(tmp, final)
            leftovers = [p.path for p in parts]
        # Önce sonucu kaydet: parça silme anlık bir kilit (antivirüs, önizleme) yüzünden başarısız olsa bile
        # indirme "tamamlandı" sayılmalı; aksi hâlde yeniden indirilir ve çift çıktı oluşur.
        ex.pop("parts", None)
        it.path = final
        it.size = os.path.getsize(final)
        self.state = "completed"
        for f in leftovers:
            for x in (f, f + ".tdm"):
                try:
                    if os.path.exists(x):
                        os.remove(x)
                except OSError:
                    pass

    def _discard_fast_parts(self):
        self._halt_parts(sync=False)
        for p, _ in self.parts:
            for f in (p.path, p.path + ".tdm"):
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except OSError:
                        pass
        self.parts, self.mode = [], None
        self.item.extra.pop("parts", None)

    # ---- yedek yol: yt-dlp'nin kendi indiricisi
    def _run_native(self):
        it, ex = self.item, self.item.extra
        self.mode = "native"
        self.phase = _t("Bağlanıyor…")
        ck = write_cookies(ex.get("cookies"))
        try:
            out_dir, name = os.path.split(it.path)
            stem = os.path.splitext(name)[0]
            args = _base_args(self.ffmpeg, ck, it.url, it.headers) + [
                "--newline", "--progress", "--quiet", "--continue", "--no-mtime",
                "-f", ex["format"], "-N", str(max(1, min(16, it.connections))),
                "--progress-template",
                "download:TDMP %(progress.downloaded_bytes)s %(progress.total_bytes)s "
                "%(progress.total_bytes_estimate)s %(progress.speed)s %(info.format_id)s",
                "--print", "after_move:TDMF %(filepath)s",
                "-o", os.path.join(out_dir, stem.replace("%", "%%") + ".%(ext)s"),
            ]
            if ex.get("ext") == "mp4" and "+" in ex["format"]:
                args += ["--merge-output-format", "mp4"]
            if self.rate:
                args += ["-r", str(int(self.rate))]
            args.append(it.url)
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         env=UTF8_ENV, creationflags=NO_WINDOW)
            final, last_err = None, []
            threading.Thread(target=self._read_err, args=(last_err,), daemon=True).start()
            for raw in self.proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                m = _PROGRESS.match(line)
                if m:
                    got, total, est, _speed, fid = m.groups()
                    got = int(float(got)) if got != "NA" else 0
                    total = int(float(total)) if total != "NA" else (int(float(est)) if est != "NA" else 0)
                    with self.lock:
                        if self.cur[0] not in (None, fid):
                            self.done_formats[self.cur[0]] = max(self.cur[1], self.cur[2])
                        self.cur = (fid, got, total)
                    self.state = "downloading"
                    self.phase = _t("Ses indiriliyor") if "+" in ex["format"] and fid == ex["format"].split("+")[1] \
                        else _t("Görüntü indiriliyor")
                    if total and got >= total:
                        self.phase = _t("Birleştiriliyor (ffmpeg)…") if "+" in ex["format"] else self.phase
                elif line.startswith("TDMF "):
                    final = line[5:].strip()
            rc = self.proc.wait()
            if self.stop_event.is_set():
                self.state = "stopped"
                return
            if rc == 0 and (not final or not os.path.isfile(final)):
                # yt-dlp başarılı ama bildirdiği yol okunamadı: dosyayı klasörde beklenen adla bul
                final = find_output(os.path.join(out_dir, stem), ex.get("ext"))
            if rc != 0 or not final or not os.path.isfile(final):
                msg = next((e for e in reversed(last_err) if "ERROR" in e), last_err[-1] if last_err else "")
                raise RuntimeError(_friendly_error(msg) if msg else
                                   (_t("İndirme bitti ama çıktı dosyası bulunamadı") if rc == 0
                                    else _t("yt-dlp beklenmedik şekilde sonlandı (kod {0})").format(rc)))
            it.path = final
            it.size = os.path.getsize(final)
            with self.lock:
                self.done_formats = {"_": it.size}
                self.cur = ("_", it.size, it.size)
            self.state = "completed"
        finally:
            if ck and os.path.exists(ck):
                os.remove(ck)

    def _read_err(self, sink):
        for raw in self.proc.stderr:
            line = raw.decode("utf-8", "replace").strip()
            if line:
                sink.append(line)
                del sink[:-20]


def _unique(path):
    base, ext = os.path.splitext(path)
    n, p = 1, path
    while os.path.exists(p):
        p = f"{base} ({n}){ext}"
        n += 1
    return p


# ------------------------------------------------------------------ yt-dlp güncelleme
GITHUB_LATEST = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"


def latest_release():
    req = urllib.request.Request(GITHUB_LATEST, headers={"User-Agent": "TurboDM", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as r:
        rel = json.load(r)
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    return {"version": rel.get("tag_name", "").strip(), "exe": assets.get("yt-dlp.exe"),
            "sums": assets.get("SHA2-256SUMS")}


def _vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "0"))


def update_available():
    """(yerel sürüm, en son sürüm, güncelleme var mı)"""
    cur, rel = version(), latest_release()
    return cur, rel["version"], _vkey(rel["version"]) > _vkey(cur)


def update(progress=None):
    """Son yt-dlp.exe'yi indirip SHA-256 ile doğrular ve %LOCALAPPDATA%\\TurboDM\\tools'a koyar."""
    rel = latest_release()
    if not rel["exe"] or not rel["sums"]:
        raise RuntimeError(_t("Sürüm dosyaları bulunamadı"))
    with urllib.request.urlopen(urllib.request.Request(rel["sums"], headers={"User-Agent": "TurboDM"}), timeout=30,
                                context=SSL_CONTEXT) as r:
        sums = r.read().decode()
    expected = next((ln.split()[0] for ln in sums.splitlines() if ln.strip().endswith(" yt-dlp.exe")), None)
    if not expected:
        raise RuntimeError(_t("Doğrulama özeti bulunamadı"))
    os.makedirs(USER_TOOLS, exist_ok=True)
    tmp = os.path.join(USER_TOOLS, "yt-dlp.exe.download")
    h = hashlib.sha256()
    req = urllib.request.Request(rel["exe"], headers={"User-Agent": "TurboDM"})
    with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            if progress:
                progress(got, total)
    if h.hexdigest().lower() != expected.lower():
        os.remove(tmp)
        raise RuntimeError(_t("İndirilen dosya doğrulanamadı (SHA-256 uyuşmuyor); güncelleme yapılmadı."))
    os.replace(tmp, os.path.join(USER_TOOLS, "yt-dlp.exe"))
    return rel["version"]
