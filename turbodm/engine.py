"""HTTP/HTTPS indirme motoru: çok bağlantılı, dinamik segmentasyonlu, devam ettirilebilir.

IDM mantığı:
  * Dosya boyutu ve "Range" desteği önce sorgulanır (probe).
  * Dosya N parçaya (segment) bölünür, her parça ayrı bir bağlantıyla indirilir.
  * Bir bağlantı kendi parçasını bitirince, kalan en büyük parçayı ikiye böler
    ve ikinci yarısını devralır (dinamik segmentasyon). Böylece yavaş bağlantılar
    sona kadar beklenmez ve tüm bağlantılar sürekli meşgul kalır.
  * Her parçanın [başlangıç, bitiş, konum] bilgisi kaydedilir; program kapansa bile
    indirme kaldığı yerden devam eder.
"""
import ftplib
import mimetypes
import os
import re
import shutil
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
from .i18n import _t

CHUNK = 64 * 1024            # tek okumada alınan veri
MIN_SPLIT = 512 * 1024       # bundan küçük kalan parça bölünmez
MAX_RETRIES = 8
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")



def _make_ssl_context():
    """HTTPS sertifikaları Windows'un kendi doğrulamasıyla (truststore) denetlenir; tarayıcılar gibi.
    Python'un yerleşik doğrulaması yalnızca Windows deposunda o an bulunan kök sertifikaları görür; Windows ise
    yeni kökleri ilk ihtiyaçta indirir. Yeni bir kök kullanan sitelerde (ör. Let's Encrypt'in yeni zinciri) eski
    yol süresi dolmuş bir çapraz imzaya düşüp "certificate has expired" hatası veriyordu."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # noqa: BLE001 (truststore yoksa Python'un kendi doğrulaması)
        return ssl.create_default_context()


SSL_CONTEXT = _make_ssl_context()


class SpeedLimiter:
    """Tüm indirmelerin paylaştığı jeton kovası (token bucket). rate=0 → sınırsız."""

    def __init__(self, rate=0):
        self.rate = rate
        self._tokens = 0.0
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def set_rate(self, rate):
        with self._lock:
            self.rate = max(0, int(rate))
            self._tokens = 0.0
            self._last = time.monotonic()

    def consume(self, n):
        with self._lock:
            rate = self.rate
            if rate <= 0:
                return
            now = time.monotonic()
            self._tokens = min(rate, self._tokens + (now - self._last) * rate)
            self._last = now
            self._tokens -= n
            deficit = -self._tokens
        if deficit > 0:
            time.sleep(deficit / rate)


def _make_sparse(f):
    """Açık dosyayı NTFS seyrek dosya yap (FSCTL_SET_SPARSE). Başarılıysa True."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        fn = k32.DeviceIoControl
        fn.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        fn.restype = wintypes.BOOL
        return bool(fn(msvcrt.get_osfhandle(f.fileno()), 0x000900C4, None, 0, None, 0,
                       ctypes.byref(wintypes.DWORD()), None))
    except Exception:  # noqa: BLE001
        return False


class ChainLimiter:
    """Birden çok sınırlayıcıyı birlikte uygular: genel hız sınırı + indirmeye özel sınır (IDM 'Hız sınırlayıcı')."""

    def __init__(self, *limiters):
        self.limiters = [x for x in limiters if x is not None]

    @property
    def rate(self):
        rates = [x.rate for x in self.limiters if x.rate]
        return min(rates) if rates else 0

    def consume(self, n):
        for x in self.limiters:
            x.consume(n)


def _open(url, headers=None, start=None, end=None, timeout=30):
    h = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "identity"}
    h.update(headers or {})
    if start is not None:
        h["Range"] = f"bytes={start}-{'' if end is None else end}"
    req = urllib.request.Request(url, headers=h)
    return urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT)


class _FtpResponse:
    """FTP veri bağlantısını HTTP yanıtı gibi gösterir: REST ile istenen konumdan başlar,
    `end`e gelince durur. Böylece aynı çok bağlantılı motor FTP'de de çalışır."""

    def __init__(self, url, start=None, end=None, timeout=30):
        self.url = url
        p = urllib.parse.urlparse(url)
        self.ftp = ftplib.FTP(timeout=timeout)
        self.ftp.connect(p.hostname, p.port or 21)
        self.ftp.login(urllib.parse.unquote(p.username or "anonymous"),
                       urllib.parse.unquote(p.password or "anonymous@"))
        self.ftp.voidcmd("TYPE I")
        try:
            self.sock = self.ftp.transfercmd("RETR " + urllib.parse.unquote(p.path), rest=start or None)
        except Exception:
            self.ftp.close()
            raise
        self.remaining = None if end is None else end - (start or 0) + 1
        self.status = 206 if start is not None else 200

    def read(self, n):
        if self.remaining is not None:
            if self.remaining <= 0:
                return b""
            n = min(n, self.remaining)
        data = self.sock.recv(n)
        if self.remaining is not None:
            self.remaining -= len(data)
        return data

    def geturl(self):
        return self.url

    def close(self):
        for c in (self.sock.close, self.ftp.close):
            try:
                c()
            except Exception:  # noqa: BLE001
                pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def is_ftp(url):
    return url.lower().startswith("ftp://")


def open_url(url, headers=None, start=None, end=None, timeout=30):
    if is_ftp(url):
        return _FtpResponse(url, start, end, timeout)
    return _open(url, headers, start, end, timeout)


def _probe_ftp(url):
    p = urllib.parse.urlparse(url)
    ftp = ftplib.FTP(timeout=30)
    try:
        ftp.connect(p.hostname, p.port or 21)
        ftp.login(urllib.parse.unquote(p.username or "anonymous"),
                  urllib.parse.unquote(p.password or "anonymous@"))
        ftp.voidcmd("TYPE I")
        size = ftp.size(urllib.parse.unquote(p.path))
        try:
            resumable = ftp.sendcmd("REST 0").startswith("350")
        except ftplib.Error:
            resumable = False
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()
    return {"final_url": url, "size": size, "resumable": resumable,
            "filename": filename_from_url(url) or "download", "content_type": "application/octet-stream"}


def filename_from_cd(cd):
    if not cd:
        return None
    m = Message()
    m["content-disposition"] = cd
    name = m.get_filename()
    return sanitize_filename(name) if name else None


def filename_from_url(url):
    path = urllib.parse.urlparse(url).path
    name = urllib.parse.unquote(os.path.basename(path))
    return sanitize_filename(name) if name else None


_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_NAME = 150  # klasör + ad + ara dosya ekleri (.f702.mp4.tdm) Windows'un 260 karakter sınırını aşmasın


def sanitize_filename(name):
    """Windows'ta geçerli, makul uzunlukta dosya adı (uzantı korunur)."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name or "").strip(" .")
    stem, ext = os.path.splitext(name)
    if len(ext) > 16 or not re.fullmatch(r"\.[\w-]*", ext or "."):
        stem, ext = name, ""
    stem = stem[:MAX_NAME - len(ext)].rstrip(" .")
    if stem.split(".")[0].upper() in _RESERVED:  # CON, NUL, COM1 … Windows'ta dosya adı olamaz
        stem = "_" + stem
    return (stem + ext) if stem else "download" + ext


def probe(url, headers=None):
    """Sunucuya 1 baytlık Range isteği atarak boyut, devam desteği ve dosya adını öğrenir."""
    if is_ftp(url):
        return _probe_ftp(url)
    try:
        resp = _open(url, headers, 0, 0)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404, 410):
            raise
        resp = _open(url, headers)  # Range'i sevmeyen sunucular için düz GET
    try:
        final = resp.geturl()
        size, resumable = None, False
        if resp.status == 206:
            m = re.search(r"/(\d+)", resp.headers.get("Content-Range", ""))
            if m:
                size, resumable = int(m.group(1)), True
        else:
            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                size = int(cl)
        ctype = resp.headers.get_content_type()
        name = filename_from_cd(resp.headers.get("Content-Disposition")) or filename_from_url(final) or "download"
    finally:
        resp.close()
    if "." not in name:
        ext = mimetypes.guess_extension(ctype or "")
        if ext and ctype not in ("text/plain", "application/octet-stream"):
            name += ext
    return {"final_url": final, "size": size, "resumable": resumable,
            "filename": name, "content_type": ctype}


TORRENT_MAX = 20 * 1024 * 1024
def not_torrent_message():
    return (_t("Site torrent dosyası yerine bir web sayfası gönderdi (indirme sayfası, giriş isteyen ya da süresi dolmuş bağlantı). Torrent'i sitedeki indirme düğmesiyle tarayıcıdan indirin: TurboDM eklentisi inen .torrent dosyasını otomatik olarak TurboDM'de açar."))


def looks_like_torrent(url, info=None):
    """Bağlantı bir .torrent dosyasına mı benziyor? (adres, sunucunun verdiği ad ya da içerik türü)"""
    info = info or {}
    names = (info.get("filename") or "", filename_from_url(url) or "")
    return (info.get("content_type") == "application/x-bittorrent"
            or any(n.lower().endswith(".torrent") for n in names))


def fetch_torrent(url, headers=None):
    """Küçük .torrent dosyasını belleğe indirir. Site torrent yerine web sayfası verirse ValueError."""
    resp = _open(url, headers)
    try:
        data = resp.read(TORRENT_MAX + 1)
    finally:
        resp.close()
    if len(data) > TORRENT_MAX:
        raise ValueError(_t("Torrent dosyası beklenenden çok büyük"))
    if not (data.startswith(b"d") and b"4:info" in data):
        raise ValueError(not_torrent_message())
    return data


class HttpTask:
    """Tek bir HTTP indirmesi. `item` üzerindeki segments listesini yerinde günceller.

    item alanları: url, headers, path, size, resumable, segments, connections
                   (isteğe bağlı) max_request: tek HTTP isteğinde istenecek en fazla bayt
    segment = [start, end(dahil), pos]  → indirilen = pos - start

    max_request: YouTube (googlevideo) gibi sunucular bir isteğin ilk ~10 MB'ından sonrasını yavaşlatır.
    Böyle sunucularda her bağlantı segmentini ≤max_request baytlık ardışık isteklerle indirir; böylece
    kısıtlamaya hiç girilmez ve bağlantı sayısı kadar hız elde edilir.
    """

    def __init__(self, item, limiter):
        self.item = item
        self.limiter = limiter
        self.max_request = int(getattr(item, "max_request", 0) or 0)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.active = set()        # şu an bir bağlantının çalıştığı segmentler (id)
        self.conn_info = {}        # id(seg) -> durum yazısı (bağlantı penceresi için)
        self.state = "connecting"  # connecting | downloading | completed | error | stopped
        self.error = None
        self._failed = False       # bir bağlantı kalıcı hata verdi (durum, işçiler bitince yayımlanır)
        # Sunucu bağlantı sınırı (IDM gibi): fazladan açılamayan bağlantılar indirmeyi bozmadan çekilir
        self.receiving = 0         # şu an veri alan bağlantı sayısı
        self.peak_receiving = 0
        self.last_data = 0.0       # herhangi bir bağlantının son veri aldığı an
        self.workers_alive = 0
        self.retired = 0           # sunucu sınırı yüzünden kapanan bağlantı sayısı
        self.last_retire = 0.0
        self._user_stop = False    # kullanıcı durdurdu (otomatik adres yenileme yapılmaz)
        self._run_thread = None

    # ---------------------------------------------------------------- dış API
    @property
    def part_path(self):
        return self.item.path + ".tdm"

    def downloaded(self):
        with self.lock:
            return sum(s[2] - s[0] for s in self.item.segments)

    def segments_snapshot(self):
        with self.lock:
            return [list(s) for s in self.item.segments]

    def bar_data(self):
        """(toplam, [[başlangıç, bitiş, konum], ...]) — parçalı ilerleme çubuğu için."""
        return self.item.size, self.segments_snapshot()

    def connections_snapshot(self):
        with self.lock:
            out = []
            for i, s in enumerate(self.item.segments):
                info = self.conn_info.get(id(s))
                if id(s) in self.active and info:
                    out.append((i + 1, s[2] - s[0], s[1] - s[0] + 1, info))
            return out

    def start(self):
        self._run_thread = threading.Thread(target=self._run, daemon=True)
        self._run_thread.start()

    def stop(self):
        self._user_stop = True
        self.stop_event.set()

    @property
    def alive(self):
        """Görev (ve tüm bağlantıları) hâlâ çalışıyor mu? Aynı segmentlerle yeni görev ancak bu False iken açılmalı."""
        return bool(self._run_thread and self._run_thread.is_alive())

    def join(self, timeout=None):
        if self._run_thread:
            self._run_thread.join(timeout)
        return not self.alive

    # ---------------------------------------------------------------- iç işleyiş
    def _run(self):
        it = self.item
        try:
            extra = getattr(it, "extra", None)
            if it.size is None or not it.segments:
                info = probe(it.url, it.headers)
                if info["final_url"] != it.url and isinstance(extra, dict):
                    # Yönlendirilen (çoğu zaman süreli, imzalı) adres: süresi dolarsa asıl adresten yenilenir
                    extra.setdefault("origin_url", it.url)
                it.url = info["final_url"]
                if it.size is not None and info["size"] not in (None, it.size):
                    # Dosya sunucuda değişmiş → baştan başla
                    it.segments = []
                it.size = info["size"]
                it.resumable = info["resumable"]
            if self.stop_event.is_set():
                self.state = "stopped"
                return
            folder = os.path.dirname(it.path) or "."
            os.makedirs(folder, exist_ok=True)
            self._check_free_space(folder)

            if not it.resumable or not it.size:
                self._single_stream()
                if self._failed:
                    self.state = "error"
                return

            if not it.segments or not os.path.exists(self.part_path):
                it.segments = self._initial_segments(it.size, it.connections)
                with open(self.part_path, "wb") as f:
                    # Seyrek dosya: bağlantılar dosyanın uzak noktalarına yazınca Windows aradaki boşluğu
                    # sıfırla doldurmak için beklemez. (Önceden 22 GB'lık dosyayı ayırmak ~20 sn, uzak noktaya
                    # ilk yazma ~8 sn bekletiyordu; seyrek dosyada ikisi de anında.) Desteklenmezse eski yöntem.
                    if not _make_sparse(f):
                        f.truncate(it.size)

            self.state = "downloading"
            refreshed = False
            # Daha önce öğrenilen sunucu sınırı: fazla bağlantıyla boşuna kapı çalınmaz
            limit = extra.get("server_conn_limit") if isinstance(extra, dict) else None
            n_workers = max(1, min(it.connections, limit) if limit else it.connections)
            while True:
                workers = []
                for _ in range(n_workers):
                    t = threading.Thread(target=self._worker, daemon=True)
                    t.start()
                    workers.append(t)
                    time.sleep(0.05)
                self._supervise(workers, extra)
                for t in workers:
                    t.join()
                # Yönlendirilen süreli adresin süresi dolduysa (403/410) asıl adresten bir kez yenile ve devam et
                origin = extra.get("origin_url") if isinstance(extra, dict) else None
                if (self._failed and not refreshed and origin and not self._user_stop
                        and any(c in (self.error or "") for c in ("HTTP 403", "HTTP 410"))):
                    refreshed = True
                    info = probe(origin, it.headers)
                    if info["size"] == it.size:
                        it.url = info["final_url"]
                        self._failed, self.error = False, None
                        self.stop_event.clear()
                        continue
                break

            # "error"/"stopped" yalnızca TÜM bağlantılar kapandıktan sonra yayımlanır: aksi hâlde yeni bir görev
            # aynı segmentlere yazmaya başlarken eski bağlantılar son parçalarını yazıp konumu kaydırabilir.
            if self._failed:
                self.state = "error"
                return
            if self.stop_event.is_set():
                self.state = "stopped"
                return
            if all(s[2] > s[1] for s in it.segments):
                self._finalize()
            else:
                self.state = "error"
                self.error = self.error or _t("Bazı parçalar tamamlanamadı")
        except Exception as e:  # noqa: BLE001
            if self._failed:
                self.state = "error"
            elif self.stop_event.is_set():
                self.state = "stopped"
            else:
                self.state = "error"
                self.error = _err_text(e)

    def _check_free_space(self, folder):
        """IDM gibi: indirme başlamadan yer yetmeyecekse hemen anlaşılır bir hata ver."""
        if not self.item.size:
            return
        try:
            free = shutil.disk_usage(folder).free
        except OSError:
            return
        with self.lock:
            done = sum(s[2] - s[0] for s in self.item.segments) if self.item.segments else 0
        need = self.item.size - done
        if need > free:
            raise OSError(28, _t("Diskte yeterli boş alan yok: {0:.2f} GB gerekli, {1:.2f} GB boş").format(need / 1073741824, free / 1073741824))

    @staticmethod
    def _initial_segments(size, n):
        n = max(1, min(n, size // MIN_SPLIT or 1))
        step = size // n
        segs = []
        for i in range(n):
            a = i * step
            b = size - 1 if i == n - 1 else (i + 1) * step - 1
            segs.append([a, b, a])
        return segs

    def _next_segment(self):
        """Boştaki bir segmenti al; yoksa en büyük kalan segmenti ikiye böl (dinamik segmentasyon)."""
        with self.lock:
            for s in self.item.segments:
                if s[2] <= s[1] and id(s) not in self.active:
                    self.active.add(id(s))
                    return s
            best, best_rem = None, 0
            for s in self.item.segments:
                rem = s[1] - s[2] + 1
                if rem > best_rem:
                    best, best_rem = s, rem
            if best is None or best_rem < MIN_SPLIT:
                return None
            # Uçuşta olan en fazla bir CHUNK verisi olabilir; ona dokunmadan böl
            mid = best[2] + CHUNK + (best_rem - CHUNK) // 2
            new = [mid, best[1], mid]
            best[1] = mid - 1
            self.item.segments.append(new)
            self.active.add(id(new))
            return new

    def _worker(self):
        with self.lock:
            self.workers_alive += 1
        retired = False
        try:
            while not self.stop_event.is_set() and not self._failed:
                seg = self._next_segment()
                if seg is None:
                    return
                try:
                    if self._download_segment(seg) == "retire":
                        retired = True  # sunucu bu bağlantıyı kabul etmiyor: parçası diğer bağlantılara kalır
                        return
                finally:
                    with self.lock:
                        self.active.discard(id(seg))
                        self.conn_info.pop(id(seg), None)
        finally:
            if not retired:  # çekilen bağlantı sayaçtan _retire'da düşüldü
                with self.lock:
                    self.workers_alive -= 1

    GROW_INTERVAL = 20  # sn: sunucu sınırı varken sorunsuz geçen bu süreden sonra bir bağlantı daha denenir

    def _supervise(self, workers, extra):
        """Sunucu bağlantı sınırı öğrenildiyse sınır sabit kalmasın: indirme sorunsuz sürerken arada bir yeni
        bağlantı denenir. Sunucu kabul ederse hız artar ve yeni sınır kaydedilir; etmezse bağlantı sessizce
        çekilir. Böylece sunucunun gerçek (ve zamanla değişebilen) sınırı bulunur."""
        it = self.item
        last_grow = time.time()
        while any(t.is_alive() for t in workers):
            if self.stop_event.wait(0.5) or self._failed:
                continue
            with self.lock:
                limited = self.retired > 0 or bool(isinstance(extra, dict) and extra.get("server_conn_limit"))
                healthy = 0 < self.workers_alive <= self.receiving
                room = self.workers_alive < it.connections
                if isinstance(extra, dict) and extra.get("server_conn_limit") and \
                        self.peak_receiving > extra["server_conn_limit"]:
                    extra["server_conn_limit"] = self.peak_receiving  # sunucu daha fazlasına izin veriyor
            now = time.time()
            if limited and healthy and room and now - max(last_grow, self.last_retire) >= self.GROW_INTERVAL:
                last_grow = now
                t = threading.Thread(target=self._worker, daemon=True)
                t.start()
                workers.append(t)

    def _others_working(self):
        """Başka bağlantılar şu an (ya da az önce) veri alıyor mu? Öyleyse sunucu çalışıyordur; açılamayan
        bağlantı sunucunun bağlantı sınırını aşan fazlalıktır."""
        return self.receiving > 0 or time.time() - self.last_data < 15

    def _retire(self, e):
        """Fazla bağlantıyı indirmeyi bozmadan kapat (en az bir bağlantı her zaman kalır). Sunucunun izin
        verdiği bağlantı sayısı kaydedilir: devam ettirince o kadar bağlantı açılır."""
        with self.lock:
            if self.workers_alive <= 1:
                return False
            self.workers_alive -= 1  # hemen düş: aynı anda çekilen iki bağlantı son bağlantıyı da götürmesin
            self.retired += 1
            self.last_retire = time.time()
            extra = getattr(self.item, "extra", None)
            if isinstance(extra, dict) and self.peak_receiving:
                extra["server_conn_limit"] = max(1, self.peak_receiving)
        return True

    def _download_segment(self, seg):
        retries = 0
        got_data = False   # bu bağlantı bu parçada veri alabildi mi
        key = id(seg)
        while not self.stop_event.is_set():
            with self.lock:
                start, end = seg[2], seg[1]
            if start > end:
                return
            # Bu istekte istenecek son bayt (max_request varsa segmenti kısa isteklere böl)
            req_end = min(end, start + self.max_request - 1) if self.max_request else end
            try:
                self.conn_info[key] = _t("Bağlanıyor…")
                resp = open_url(self.item.url, self.item.headers, start, req_end)
                if resp.status != 206:
                    resp.close()
                    raise IOError(_t("Sunucu parça (Range) isteğini reddetti"))
                self.conn_info[key] = _t("Veri alınıyor")
                with self.lock:
                    self.receiving += 1
                    self.peak_receiving = max(self.peak_receiving, self.receiving)
                try:
                    with resp, open(self.part_path, "r+b") as f:
                        f.seek(start)
                        while not self.stop_event.is_set():
                            with self.lock:
                                # segment başka bir bağlantı tarafından bölünmüş olabilir: seg[1] küçülür
                                remaining = min(seg[1], req_end) - seg[2] + 1
                            if remaining <= 0:
                                break
                            data = resp.read(min(CHUNK, remaining))
                            if not data:
                                raise IOError(_t("Bağlantı erken kapandı"))
                            self.limiter.consume(len(data))
                            with self.lock:
                                allowed = min(seg[1], req_end) - seg[2] + 1  # başka bağlantı bölmüş olabilir
                            if allowed <= 0:
                                break
                            data = data[:allowed]
                            f.write(data)
                            got_data = True
                            self.last_data = time.time()
                            with self.lock:
                                seg[2] += len(data)
                finally:
                    with self.lock:
                        self.receiving -= 1
                retries = 0
            except Exception as e:  # noqa: BLE001
                if self.stop_event.is_set():
                    return
                if _fatal(e):
                    self._fail(e)
                    return
                retries += 1
                # Sunucu bağlantı sınırı: diğerleri veri alırken bu bağlantı açılamıyorsa fazlalıktır. Tek bir
                # bağlantının hatası artık tüm indirmeyi düşürmez; yalnızca hiçbir bağlantı çalışmıyorsa hata.
                if self._others_working() and (retries >= 2 and not got_data or retries > MAX_RETRIES):
                    if self._retire(e):
                        return "retire"
                if retries > MAX_RETRIES:
                    self._fail(e)
                    return
                self.conn_info[key] = _t("Yeniden deneniyor ({0}/{1}): {2}").format(retries, MAX_RETRIES, _err_text(e))
                self.stop_event.wait(_retry_delay(e, retries))

    def _single_stream(self):
        """Range desteklemeyen / boyutu bilinmeyen sunucular: tek bağlantı, devam yok."""
        it = self.item
        retries = 0
        while not self.stop_event.is_set():
            it.segments = [[0, (it.size or 1 << 62) - 1, 0]]
            seg = it.segments[0]
            self.active = {id(seg)}
            self.conn_info[id(seg)] = _t("Veri alınıyor (tek bağlantı)")
            self.state = "downloading"
            try:
                with open_url(it.url, it.headers) as resp, open(self.part_path, "wb") as f:
                    # Beklenen boyut: Content-Length ya da ön sorgudan. Bağlantı erken kapanırsa read() hata
                    # vermeden b"" döndürür; yarım dosyanın "tamamlandı" sayılmaması için sonda karşılaştırılır.
                    cl = getattr(resp, "headers", None) and resp.headers.get("Content-Length")
                    expected = int(cl) if cl and cl.isdigit() else it.size
                    while not self.stop_event.is_set():
                        data = resp.read(CHUNK)
                        if not data:
                            break
                        self.limiter.consume(len(data))
                        f.write(data)
                        with self.lock:
                            seg[2] += len(data)
                if self.stop_event.is_set():
                    self.state = "stopped"
                    it.segments = []  # devam edilemez
                    return
                if expected and seg[2] < expected:
                    raise IOError(_t("Bağlantı erken kapandı ({0}/{1} bayt)").format(seg[2], expected))
                it.size = seg[2]
                seg[1] = seg[2] - 1
                self._finalize()
                return
            except Exception as e:  # noqa: BLE001
                if self.stop_event.is_set():
                    break  # kullanıcı durdurdu: hata değil
                retries += 1
                if retries > MAX_RETRIES or _fatal(e):
                    self._fail(e)
                    return
                self.stop_event.wait(min(2 ** retries, 30))
        self.state = "stopped"

    def _finalize(self):
        final = self.item.path
        if os.path.exists(final):
            os.remove(final)
        os.replace(self.part_path, final)
        with self.lock:
            size = self.item.size or 0
            self.item.segments = [[0, size - 1, size]] if size else []
        self.state = "completed"

    def _fail(self, e):
        self.error = _err_text(e)
        self._failed = True
        self.stop_event.set()


def _retry_delay(e, retries):
    """Yeniden deneme beklemesi; sunucu 429/503 ile 'Retry-After' bildirdiyse ona uyulur (en çok 60 sn)."""
    if isinstance(e, urllib.error.HTTPError) and e.code in (429, 503):
        ra = (e.headers or {}).get("Retry-After", "") if hasattr(e, "headers") else ""
        if str(ra).isdigit():
            return min(int(ra), 60)
    return min(2 ** retries, 30)


def _fatal(e):
    """Yeniden denemenin anlamsız olduğu hatalar: kalıcı HTTP/FTP reddi ve disk sorunları."""
    return ((isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 404, 410))
            or isinstance(e, ftplib.error_perm) or disk_error(e) is not None)


def disk_error(e):
    """Yeniden denemenin işe yaramayacağı disk hataları için kullanıcıya anlaşılır metin; değilse None."""
    if not isinstance(e, OSError) or isinstance(e, (urllib.error.URLError, ConnectionError, TimeoutError)):
        return None
    win = getattr(e, "winerror", None)
    if e.errno == 28 or win in (39, 112):
        return _t("Diskte yeterli boş alan yok")
    if e.errno in (13, 30) or win in (5, 19, 32):
        return _t("Klasöre yazılamıyor (izin yok ya da dosya kullanımda): {0}").format(getattr(e, 'filename', '') or '').strip(": ")
    if win in (3, 15, 21) or e.errno == 2 and getattr(e, "filename", None):
        return _t("Kayıt klasörüne ulaşılamıyor (sürücü çıkarılmış olabilir): {0}").format(e.filename)
    if win == 206 or e.errno == 36:
        return _t("Dosya yolu çok uzun; daha kısa bir klasör seçin")
    return None


def _err_text(e):
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code} {e.reason}"
    if isinstance(e, urllib.error.URLError):
        return _t("Bağlantı hatası: {0}").format(e.reason)
    if isinstance(e, TimeoutError) or "timed out" in str(e):
        return _t("Sunucu yanıt vermiyor (zaman aşımı)")
    if isinstance(e, ConnectionError):
        return _t("Bağlantı koptu")
    return disk_error(e) or str(e) or e.__class__.__name__
