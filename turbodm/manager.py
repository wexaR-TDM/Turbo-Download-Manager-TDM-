"""İndirme yöneticisi: liste, kalıcılık, kuyruk, zamanlayıcı, kategoriler, hız sınırı."""
import copy
import json
import os
import shutil
import threading
import time
import uuid
from datetime import datetime

from . import torrent as tmod
from .engine import ChainLimiter, HttpTask, SpeedLimiter
from .hls import HlsTask, find_ffmpeg
from . import convert, ytdlp
from . import i18n
from .i18n import _t

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "TurboDM")
TORRENT_DIR = os.path.join(APP_DIR, "torrents")
DEFAULT_ROOT = os.path.join(os.path.expanduser("~"), "Downloads", "TurboDM")

# anahtar: (görünen ad, klasör, uzantılar)
CATEGORIES = {}


@i18n.on_change
def _texts():
    CATEGORIES.update({
    "compressed": (_t("Sıkıştırılmış"), "Compressed",
                   "zip rar 7z tar gz tgz bz2 xz iso cab arj lzh z ace".split()),
    "documents": (_t("Belgeler"), "Documents",
                  "pdf doc docx xls xlsx ppt pptx txt rtf odt ods epub csv".split()),
    "music": (_t("Müzik"), "Music", "mp3 wav flac aac ogg wma m4a opus aif aiff".split()),
    "programs": (_t("Programlar"), "Programs", "exe msi apk dmg deb rpm msix appx bat".split()),
    "video": (_t("Video"), "Video",
              "mp4 mkv avi mov wmv flv webm m4v mpg mpeg 3gp ts m2ts".split()),
    "torrent": (_t("Torrent"), "Torrent", []),
    "general": (_t("Genel"), "General", []),
    })

DEFAULT_SETTINGS = {
    "download_root": DEFAULT_ROOT,
    "connections": 8,
    "max_concurrent": 3,
    "speed_limit_kb": 0,
    "clipboard_monitor": True,
    "server_port": 9614,
    "torrent_port": 0,          # 0: ilk açılışta rastgele seçilir (6881 bazı servis sağlayıcılarda yavaşlatılır)
    "torrent_port_random": False,
    "torrent_upload_kb": 0,     # elle yükleme sınırı (0 = sınırsız ya da otomatik)
    "torrent_upload_auto": True,  # indirirken yüklemeyi otomatik sınırla: dolan yükleme hattı indirmeyi yavaşlatır
    "seed_after_complete": False,
    "show_complete_dialog": True,
    "schedule_enabled": False,
    "schedule_start": "02:00",
    "schedule_stop": "07:00",
    "ffmpeg_path": "",
    "auto_update_check": True,
    "language": "en",           # tr | en | de | fr | es | ar | it (kurulumda seçilir)
    "theme": "auto",            # auto (Windows ile aynı) | light | dark
    "last_update_check": 0,
    "update_repo": "",      # boşsa appinfo.UPDATE_REPO kullanılır
}

CATCH_EXTS = set(e for k, v in CATEGORIES.items() for e in v[2])


def category_for(filename):
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    for key, (_, _, exts) in CATEGORIES.items():
        if ext in exts:
            return key
    return "general"


class DownloadItem:
    FIELDS = ("id", "kind", "url", "path", "category", "size", "resumable", "segments",
              "headers", "description", "added", "last_try", "status", "error",
              "connections", "in_queue", "done_bytes", "source", "extra")

    def __init__(self, **kw):
        self.id = kw.get("id") or uuid.uuid4().hex[:12]
        self.kind = kw.get("kind", "http")          # http (http/https/ftp) | hls | torrent
        self.extra = kw.get("extra") or {}          # hls: parça durumu, torrent: dosya öncelikleri
        self.url = kw.get("url", "")
        self.path = kw.get("path", "")              # http: dosya yolu, torrent: kayıt klasörü
        self.category = kw.get("category", "general")
        self.size = kw.get("size")
        self.resumable = kw.get("resumable", True)
        self.segments = kw.get("segments") or []
        self.headers = kw.get("headers") or {}
        self.description = kw.get("description", "")
        self.added = kw.get("added") or time.time()
        self.last_try = kw.get("last_try")
        self.status = kw.get("status", "stopped")
        self.error = kw.get("error")
        self.connections = kw.get("connections", 8)
        self.in_queue = kw.get("in_queue", False)
        self.done_bytes = kw.get("done_bytes", 0)
        self.source = kw.get("source", "")          # torrent: magnet ya da .torrent kopyası
        # çalışma zamanı (kaydedilmez)
        self.task = None
        self.speed = 0.0
        self.ul_speed = 0.0
        self.peers = 0
        self.seeds = 0
        self.name = kw.get("name") or ""
        self._last_bytes = None
        self._last_t = None

    @property
    def filename(self):
        if self.kind == "torrent":
            return self.name or _t("(meta veri bekleniyor)")
        return os.path.basename(self.path)

    def to_dict(self):
        d = {k: getattr(self, k) for k in self.FIELDS}
        d["extra"] = copy.deepcopy(self.extra)
        for k in ("cookies", "streams", "streams_t"):  # oturum çerezleri / geçici akış adresleri diske yazılmaz
            d["extra"].pop(k, None)
        d["name"] = self.name
        if self.status in ("seeding", "converting"):  # yarıda kalan dönüştürme: asıl dosya duruyor
            d["status"] = "completed"
        elif self.status in ("downloading", "connecting"):
            d["status"] = "queued" if self.in_queue else "stopped"
        return d

    def eta(self):
        if not self.size or self.speed <= 1:
            return None
        return max(0, (self.size - self.done_bytes) / self.speed)


class Manager:
    def __init__(self):
        os.makedirs(TORRENT_DIR, exist_ok=True)
        # bağlantıdan alınıp dosya seçimi bekleyen geçici .torrent'ler (eklenince TORRENT_DIR'e kopyalanır)
        shutil.rmtree(os.path.join(TORRENT_DIR, "gelen"), ignore_errors=True)
        self.settings = dict(DEFAULT_SETTINGS)
        self.settings.update(self._load_json("settings.json", {}))
        if not self.settings["torrent_port_random"] and self.settings["torrent_port"] in (0, 6881):
            # bilinen BitTorrent portu yerine bu bilgisayara özgü rastgele bir port (bir kez seçilir)
            import random
            self.settings["torrent_port"] = random.randint(49160, 65000)
            self.settings["torrent_port_random"] = True
        self._auto_ul = None    # otomatik yükleme sınırının son uygulanan değeri
        self._auto_ul_t = 0
        self.items = {}
        self.order = []
        self.limiter = SpeedLimiter(self.settings["speed_limit_kb"] * 1024)
        self.queue_running = False
        self.events = []        # GUI'ye bildirimler: ("completed"|"error", item)
        self._last_save = 0
        self._sched_last = None
        self.torrents = None
        self.torrent_error = None
        if tmod.AVAILABLE:
            try:
                self.torrents = tmod.TorrentEngine(
                    self.settings["torrent_port"], 0, self.settings["torrent_upload_kb"] * 1024)
                self.torrents.resume_cb = self._on_resume_data
                self.torrents.error_cb = self._on_torrent_error
            except Exception as e:  # noqa: BLE001
                self.torrent_error = str(e)
        else:
            self.torrent_error = _t("libtorrent yüklü değil")
        self._apply_torrent_limits()
        for d in self._load_json("downloads.json", []):
            it = DownloadItem(**d)
            self.items[it.id] = it
            self.order.append(it.id)
            if it.kind == "torrent" and self.torrents and it.status != "completed":
                self._attach_torrent(it, paused=True)

    # ------------------------------------------------------------ kalıcılık
    def _load_json(self, name, default):
        """Kayıt bozuksa (elektrik kesintisi, disk hatası) bir önceki sağlam kopya (.bak) yüklenir;
        bozuk dosya silinmez, incelenebilsin diye kenara alınır. Liste sessizce kaybolmaz."""
        p = os.path.join(APP_DIR, name)
        for path in (p, p + ".bak"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, type(default)):
                    return data
                raise ValueError(_t("beklenmeyen biçim"))
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                try:
                    os.replace(path, path + time.strftime(".bozuk-%Y%m%d-%H%M%S"))
                except OSError:
                    pass
        return default

    def _save_json(self, name, data):
        p = os.path.join(APP_DIR, name)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())  # elektrik kesilse bile yarım yazılmış dosya kalmasın
        if os.path.exists(p):
            try:
                os.replace(p, p + ".bak")  # bir önceki sağlam sürüm
            except OSError:
                pass
        os.replace(tmp, p)

    def save(self):
        data = []
        for i in self.order:
            it = self.items[i]
            if it.task:
                with it.task.lock:  # segment listesi tutarlı kopyalansın
                    d = it.to_dict()
                    d["segments"] = [list(s) for s in it.segments]
            else:
                d = it.to_dict()
            data.append(d)
        self._save_json("downloads.json", data)
        self._save_json("settings.json", self.settings)
        self._last_save = time.time()

    def apply_settings(self):
        self.limiter.set_rate(self.settings["speed_limit_kb"] * 1024)
        self._apply_torrent_limits()
        self.save()

    def _apply_torrent_limits(self):
        if self.torrents:
            self._auto_ul = None
            self.torrents.set_limits(self.settings["speed_limit_kb"] * 1024, self.upload_limit())

    AUTO_UL_MIN, AUTO_UL_MAX = 150 * 1024, 2 * 1024 * 1024

    def upload_limit(self):
        """Torrent yükleme sınırı (bayt/sn, 0 = sınırsız). Elle verilmişse o; değilse indirme sürerken
        otomatik: indirme hızının ~%8'i + 100 KB/s (150 KB/s – 2 MB/s). Yükleme hattı dolunca karşı eşlere
        giden onaylar gecikir ve indirme de yavaşlar; bu pay paylaşım (karşılıklılık) için yeterlidir.
        Yalnızca paylaşım (seed) varken sınır yoktur."""
        manual = self.settings["torrent_upload_kb"] * 1024
        if manual or not self.settings["torrent_upload_auto"]:
            return manual
        down = [i for i in self.items.values() if i.kind == "torrent" and i.status in ("downloading", "connecting")]
        if not down:
            return 0
        rate = sum(i.speed for i in down)
        return int(min(self.AUTO_UL_MAX, max(self.AUTO_UL_MIN, rate * 0.08 + 100 * 1024)))

    def _tick_upload_limit(self, now):
        if not self.torrents or now - self._auto_ul_t < 3:
            return
        self._auto_ul_t = now
        ul = self.upload_limit()
        if self._auto_ul is None or abs(ul - self._auto_ul) > max(32 * 1024, 0.1 * self._auto_ul):
            self._auto_ul = ul
            self.torrents.set_limits(self.settings["speed_limit_kb"] * 1024, ul)

    # ------------------------------------------------------------ ekleme
    def category_dir(self, cat):
        return os.path.join(self.settings["download_root"], CATEGORIES[cat][1])

    def unique_path(self, path):
        taken = {it.path.lower() for it in self.items.values() if it.kind != "torrent"}
        base, ext = os.path.splitext(path)
        n, p = 1, path
        while os.path.exists(p) or os.path.exists(p + ".tdm") or os.path.exists(p + ".tdm_parts") or p.lower() in taken:
            p = f"{base} ({n}){ext}"
            n += 1
        return p

    def add_http(self, url, path, category=None, headers=None, description="",
                 start=True, size=None, resumable=True):
        it = DownloadItem(kind="http", url=url, path=self.unique_path(path),
                          category=category or category_for(path), headers=headers or {},
                          description=description, size=size, resumable=resumable,
                          connections=self.settings["connections"])
        it.in_queue = not start
        it.status = "queued" if not start else "stopped"
        self._register(it)
        if start:
            self.start(it.id)
        return it

    def ffmpeg(self):
        return find_ffmpeg(self.settings.get("ffmpeg_path"))

    def add_hls(self, url, media_url, audio_url, path, headers=None, description="", start=True):
        it = DownloadItem(kind="hls", url=url, path=self.unique_path(path), category="video",
                          headers=headers or {}, description=description,
                          connections=self.settings["connections"],
                          extra={"media_url": media_url, "audio_url": audio_url, "done": [], "bytes": 0})
        it.in_queue = not start
        it.status = "queued" if not start else "stopped"
        self._register(it)
        if start:
            self.start(it.id)
        return it

    def add_ytdlp(self, url, path, choice, title="", headers=None, cookies=None, description="", start=True):
        """Site videosu (YouTube vb.). choice: ytdlp.build_choices çıktısından bir seçenek."""
        it = DownloadItem(kind="ytdlp", url=url, path=self.unique_path(path),
                          category="video" if choice.get("height") else "music",
                          headers=headers or {}, description=description or choice.get("label", ""),
                          connections=self.settings["connections"], size=choice.get("size") or None,
                          extra={"format": choice["format"], "ext": choice.get("ext", "mp4"),
                                 "title": title, "cookies": cookies or [], "size": choice.get("size") or 0,
                                 "streams": choice.get("streams"), "streams_t": time.time()})
        it.in_queue = not start
        it.status = "queued" if not start else "stopped"
        self._register(it)
        if start:
            self.start(it.id)
        return it

    def add_torrent(self, source, save_dir, start=True, description="", priorities=None, probe_key=None):
        """source: magnet ya da .torrent yolu. probe_key: dosya seçimi için meta verisi
        önceden alınmış magnet (TorrentEngine.probe_start) → aynı oturum devralınır."""
        if not self.torrents:
            raise RuntimeError(self.torrent_error or _t("Torrent desteği yok"))
        it = DownloadItem(kind="torrent", category="torrent", path=save_dir, description=description)
        if priorities:
            it.extra["priorities"] = list(priorities)
        if source.startswith("magnet:"):
            it.source = it.url = source
            if probe_key:
                dst = os.path.join(TORRENT_DIR, it.id + ".torrent")
                if self.torrents.probe_save_torrent(probe_key, dst):
                    it.source = dst  # meta veri hazır: yeniden başlatınca tekrar beklemesin
        else:
            dst = os.path.join(TORRENT_DIR, it.id + ".torrent")
            shutil.copyfile(source, dst)
            it.source = dst
            it.url = os.path.basename(source)
        if it.source.endswith(".torrent"):
            it.name = tmod.lt.torrent_info(it.source).name()
        it.in_queue = not start
        it.status = "queued" if not start else "stopped"
        if probe_key:
            self.torrents.probe_adopt(probe_key, it.id, save_dir, priorities)
        else:
            self._attach_torrent(it, paused=True)
            if it.status == "error":
                raise RuntimeError(it.error)
        self._register(it)
        if start:
            self.start(it.id)
        return it

    def set_torrent_priorities(self, iid, priorities):
        it = self.items.get(iid)
        if it and self.torrents:
            it.extra["priorities"] = list(priorities)
            self.torrents.set_priorities(iid, priorities)

    def _register(self, it):
        self.items[it.id] = it
        self.order.append(it.id)
        self.save()

    def _resume_file(self, it):
        return os.path.join(TORRENT_DIR, it.id + ".fastresume")

    def _attach_torrent(self, it, paused):
        try:
            self.torrents.add(it.id, it.source, it.path, self._resume_file(it), paused=paused,
                              priorities=it.extra.get("priorities"))
        except Exception as e:  # noqa: BLE001
            it.status, it.error = "error", str(e)

    def _on_resume_data(self, iid, data):
        it = self.items.get(iid)
        if it:
            with open(self._resume_file(it), "wb") as f:
                f.write(data)

    def _on_torrent_error(self, iid, msg):
        it = self.items.get(iid)
        if it:
            it.error = msg

    # ------------------------------------------------------------ kontrol
    def start(self, iid):
        it = self.items.get(iid)
        if not it or it.status in ("downloading", "connecting", "seeding", "converting"):
            return
        if it.status == "completed" and (it.kind != "torrent" or not self.settings["seed_after_complete"]):
            return
        it.error = None
        it.last_try = time.time()
        if it.kind in ("http", "hls", "ytdlp") and it.task is not None and getattr(it.task, "alive", False):
            # Duraklat'tan hemen sonra Devam: eski bağlantılar henüz kapanmadı. Aynı segmentlere iki görev
            # yazarsa dosyaya boşluk karışır → eski görev bitince _tick_http yeniden başlatır.
            it.task.stop()
            it.pending_start = True
            it.status = "connecting"
            return
        if it.kind in ("http", "hls", "ytdlp"):
            it.connections = self.settings["connections"]
            lim = ChainLimiter(self.limiter, self.item_limiter(it))
            if it.kind == "http":
                it.task = HttpTask(it, lim)
            elif it.kind == "hls":
                it.task = HlsTask(it, lim, self.ffmpeg())
            else:
                it.task = ytdlp.YtdlpTask(it, lim, self.ffmpeg())
            it.status = "connecting"
            it.task.start()
        else:
            if not self.torrents:
                it.status, it.error = "error", self.torrent_error
                return
            if iid not in self.torrents.handles:
                self._attach_torrent(it, paused=True)
            self.torrents.resume(iid)
            it.status = "seeding" if it.status == "completed" else "connecting"

    def item_limiter(self, it):
        """İndirmeye özel hız sınırı (IDM'deki indirme penceresi → Hız sınırlayıcı). Çalışırken değiştirilebilir."""
        if getattr(it, "limiter", None) is None:
            it.limiter = SpeedLimiter(int(it.extra.get("speed_limit_kb") or 0) * 1024)
        return it.limiter

    def set_item_limit(self, iid, kb):
        it = self.items.get(iid)
        if it:
            it.extra["speed_limit_kb"] = int(kb or 0)
            self.item_limiter(it).set_rate(int(kb or 0) * 1024)

    def stop(self, iid):
        it = self.items.get(iid)
        if not it:
            return
        if it.kind != "torrent":
            it.pending_start = False
            if it.task:
                it.task.stop()
            if it.status in ("downloading", "connecting", "queued"):
                it.status = "stopped"
        else:
            if self.torrents:
                self.torrents.pause(iid)
            it.status = "completed" if it.status in ("completed", "seeding") else "stopped"
        it.speed = 0

    def stop_all(self):
        self.queue_running = False
        for iid in self.order:
            self.stop(iid)

    def remove(self, iid, delete_file=False):
        it = self.items.pop(iid, None)
        if not it:
            return
        self.order.remove(iid)
        if it.kind != "torrent":
            files, dirs = [], []
            if delete_file:
                files.append(it.path)
            if delete_file or it.status != "completed":
                files.append(it.path + ".tdm")
                dirs.append(it.path + ".tdm_parts")
                if it.kind == "ytdlp":
                    files += ytdlp.partial_files(it.path)
                    files += [p["path"] + s for p in (it.extra.get("parts") or {}).values()
                              if p.get("path") for s in ("", ".tdm")]
            task = it.task
            if task:
                task.stop()
            # Çalışan bağlantılar dosyaları açık tutar (Windows silmeye izin vermez). Arayüzü dondurmadan,
            # bağlantılar kapanınca arka planda sil.
            threading.Thread(target=_remove_later, args=(task, files, dirs), daemon=True).start()
        else:
            if self.torrents:
                self.torrents.remove(iid, delete_file)
            _try_remove(self._resume_file(it))
            if it.source.startswith(TORRENT_DIR):
                _try_remove(it.source)
        self.save()

    def set_queue(self, iid, flag):
        it = self.items.get(iid)
        if it and it.status != "completed":
            it.in_queue = flag
            if flag and it.status == "stopped":
                it.status = "queued"
            elif not flag and it.status == "queued":
                it.status = "stopped"

    def start_queue(self):
        self.queue_running = True
        for it in self.items.values():
            if it.in_queue and it.status in ("stopped", "error"):
                it.status = "queued"

    def stop_queue(self):
        self.queue_running = False
        for it in self.items.values():
            if it.in_queue and it.status in ("downloading", "connecting"):
                self.stop(it.id)
                it.status = "queued"

    # ------------------------------------------------------------ periyodik
    def tick(self):
        now = time.time()
        for it in list(self.items.values()):
            if it.status == "converting":
                self._tick_convert(it)
            elif it.kind != "torrent":
                self._tick_http(it, now)
            else:
                self._tick_torrent(it, now)
        if self.torrents:
            self.torrents.pump_alerts()
        self._tick_upload_limit(now)
        self._tick_queue()
        self._tick_schedule()
        if now - self._last_save > 5:
            if self.torrents:
                self.torrents.request_resume_data()
            self.save()

    def _speed(self, it, now, total):
        if it._last_bytes is None:
            it._last_bytes, it._last_t = total, now
            return
        dt = now - it._last_t
        if dt >= 0.5:
            inst = max(0, total - it._last_bytes) / dt
            it.speed = inst if it.speed == 0 else it.speed * 0.7 + inst * 0.3
            it._last_bytes, it._last_t = total, now

    def _tick_http(self, it, now):
        t = it.task
        if not t:
            return
        it.done_bytes = t.downloaded()
        if it.kind in ("hls", "ytdlp") and t.state != "completed":
            it.size = t.estimated_size() or it.size
        self._speed(it, now, it.done_bytes)
        if t.state == "downloading" and it.status == "connecting":
            it.status = "downloading"
        elif t.state == "completed":
            it.status, it.task, it.speed, it.in_queue = "completed", None, 0, False
            if getattr(t, "note", None):
                it.description = (it.description + " " + t.note).strip()
            it.done_bytes = it.size or it.done_bytes
            if it.extra.get("convert") in convert.FORMATS and it.extra.get("convert"):
                self._start_convert(it)  # "tamamlandı" bildirimi dönüştürme bitince
                return
            self.events.append(("completed", it))
            self.save()
        elif t.state in ("error", "stopped") and getattr(it, "pending_start", False):
            # kullanıcı bu arada Devam dedi: eski görev artık tamamen kapandı → şimdi başlat
            it.pending_start = False
            it.task, it.speed, it.status = None, 0, "stopped"
            self.start(it.id)
        elif t.state == "error":
            it.status, it.error, it.task, it.speed = "error", t.error, None, 0
            self.events.append(("error", it))
            self.save()
        elif t.state == "stopped":
            it.task, it.speed = None, 0
            if it.status not in ("queued",):
                it.status = "stopped"

    # ------------------------------------------------------------ biçim dönüştürme (indirme bitince)
    def _start_convert(self, it):
        it.status = "converting"
        it._conv = None
        fmt, src, ff = it.extra["convert"], it.path, self.ffmpeg()

        def work():
            try:
                it._conv = (convert.convert(ff, src, fmt), None)
            except Exception as e:  # noqa: BLE001
                it._conv = (None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _tick_convert(self, it):
        res = getattr(it, "_conv", None)
        if res is None:
            return
        it._conv = None
        dst, err = res
        it.status = "completed"
        it.extra.pop("convert", None)
        if dst:
            it.path = dst
            try:
                it.size = it.done_bytes = os.path.getsize(dst)
            except OSError:
                pass
        else:
            it.description = (it.description + _t(" ({0}; asıl dosya korundu)").format(err)).strip()
        self.events.append(("completed", it))
        self.save()

    def _tick_torrent(self, it, now):
        if not self.torrents:
            return
        st = self.torrents.status(it.id)
        if not st:
            return
        it.name = st["name"] or it.name
        if st["size"]:
            it.size = st["size"]
        it.done_bytes = st["done"]
        it.speed, it.ul_speed = st["dl_rate"], st["ul_rate"]
        it.peers, it.seeds = st["peers"], st["seeds"]
        if it.status in ("stopped", "queued", "completed") and st["paused"]:
            it.speed = it.ul_speed = 0
            return
        if st["error"]:
            it.status, it.error = "error", st["error"]
            return
        if st["finished"]:
            it.error = None
            if it.status not in ("completed", "seeding"):
                it.in_queue = False
                self.events.append(("completed", it))
                self.torrents.request_resume_data(it.id)
                if self.settings["seed_after_complete"]:
                    it.status = "seeding"
                else:
                    self.torrents.pause(it.id)
                    it.status = "completed"
                self.save()
        elif not st["paused"]:
            it.status = "downloading" if st["state"] == "downloading" and it.speed > 0 else "connecting"
            it.error = st["state_text"] if it.status == "connecting" else None

    def _tick_queue(self):
        if not self.queue_running:
            return
        active = [i for i in self.items.values()
                  if i.in_queue and i.status in ("downloading", "connecting")]
        free = self.settings["max_concurrent"] - len(active)
        waiting = [self.items[i] for i in self.order
                   if self.items[i].in_queue and self.items[i].status == "queued"]
        for it in waiting[:max(0, free)]:
            it.status = "stopped"
            self.start(it.id)
        if not waiting and not active:
            self.queue_running = False
            self.events.append(("queue_done", None))

    def _tick_schedule(self):
        if not self.settings["schedule_enabled"]:
            return
        hm = datetime.now().strftime("%H:%M")
        if hm == self._sched_last:
            return
        self._sched_last = hm
        if hm == self.settings["schedule_start"]:
            self.start_queue()
            self.events.append(("info", _t("Zamanlayıcı: kuyruk başlatıldı")))
        elif hm == self.settings["schedule_stop"]:
            self.stop_queue()
            self.events.append(("info", _t("Zamanlayıcı: kuyruk durduruldu")))

    def total_speed(self):
        return sum(i.speed for i in self.items.values())

    def resume_interrupted(self):
        """Güncelleme için kapatılmadan önce inmekte olan indirmeleri yeniden başlat (--resume)."""
        for iid in list(self.order):
            it = self.items[iid]
            if it.extra.pop("resume_after_restart", False):
                self.start(iid)

    def shutdown(self):
        for it in self.items.values():
            # kapanırken inmekte olanlar işaretlenir: güncelleme sonrası --resume ile kaldığı yerden sürer
            if it.status in ("downloading", "connecting"):
                it.extra["resume_after_restart"] = True
            else:
                it.extra.pop("resume_after_restart", None)
            if it.task:
                try:  # bir görevin hatası kaydı ve kapanışı engellemesin
                    it.task.stop()
                except Exception:  # noqa: BLE001
                    pass
        if self.torrents:
            self.torrents.request_resume_data()
            time.sleep(0.5)
            self.torrents.pump_alerts()
            self.torrents.shutdown()
        # bağlantıların son baytları yazması için kısa bekleme
        time.sleep(0.3)
        self.save()


def _remove_later(task, files, dirs):
    if task is not None and hasattr(task, "join"):
        task.join(60)
    for _ in range(10):  # antivirüs/dizinleyici anlık kilit tutabilir
        for p in files:
            _try_remove(p)
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)
        if not any(os.path.exists(p) for p in files + dirs):
            return
        time.sleep(1)


def _try_remove(p):
    try:
        if p and os.path.isfile(p):
            os.remove(p)
    except OSError:
        pass
