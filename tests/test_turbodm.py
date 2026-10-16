"""TurboDM test paketi — yalnızca yerel sunucular (127.0.0.1), internete çıkmaz.

Çalıştırma:   python -m unittest tests.test_turbodm -v
              (ya da: powershell -ExecutionPolicy Bypass -File tests\\run_tests.ps1)
"""
import atexit
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ["TURBODM_LANG"] = "tr"  # testler Türkçe metinlerle yazıldı; sistem dilinden bağımsız
os.makedirs(os.path.join(ROOT, "build", "tmp"), exist_ok=True)
TMP = tempfile.mkdtemp(prefix="tdm_tests_", dir=os.path.join(ROOT, "build", "tmp"))  # proje içinde
atexit.register(shutil.rmtree, TMP, True)  # bilgisayarda test kalıntısı bırakma
os.environ["APPDATA"] = os.path.join(TMP, "appdata")  # gerçek kullanıcı verisine dokunma
sys.path.insert(0, ROOT)

from turbodm import engine, hls, manager, server, ytdlp  # noqa: E402
from turbodm.engine import ChainLimiter, HttpTask, SpeedLimiter, probe, sanitize_filename  # noqa: E402

FF = hls.find_ffmpeg()


# ---------------------------------------------------------------------------------------------- yardımcılar
class FakeServer:
    """Davranışı ayarlanabilir yerel HTTP sunucusu (Range, yönlendirme, kopma, 403, boyutsuz yanıt…)."""

    def __init__(self):
        self.files = {}            # yol -> bytes
        self.range = True          # Range desteği
        self.delay = 0.0           # 64 KB başına bekleme (yavaş sunucu)
        self.drop_after = None     # her yanıtta bu kadar bayttan sonra bağlantıyı kopar (bir kez/istek)
        self.drop_budget = 0       # kaç istek kopsun
        self.chunked = set()       # Content-Length göndermeden akıtılacak yollar
        self.redirects = {}        # yol -> hedef (callable ya da str)
        self.forbidden = set()     # 403 dönecek tam yollar (sorgu dahil)
        self.cd = {}               # yol -> Content-Disposition
        self.lie_length = {}       # yol -> (ilan edilen boyut) sonra erken kapat
        self.max_conns = 0         # >0: aynı anda bundan fazla indirme bağlantısını 503 ile reddet (gofile gibi)
        self.open_conns = 0
        self.requests = []
        outer = self
        conn_lock = threading.Lock()

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                outer.requests.append((self.path, self.headers.get("Range")))
                path = self.path.split("?")[0]
                if self.path in outer.forbidden:
                    return self._send(403, b"")
                if path in outer.redirects:
                    tgt = outer.redirects[path]
                    tgt = tgt() if callable(tgt) else tgt
                    self.send_response(302)
                    self.send_header("Location", tgt)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                data = outer.files.get(path)
                if data is None:
                    return self._send(404, b"")
                if path in outer.lie_length:
                    self.send_response(200)
                    self.send_header("Content-Length", str(outer.lie_length[path]))
                    self.end_headers()
                    self.wfile.write(data)
                    self.close_connection = True
                    return
                if path in outer.chunked:
                    self.send_response(200)
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(data)
                    self.close_connection = True
                    return
                rng = self.headers.get("Range") if outer.range else None
                a, b = 0, len(data) - 1
                if rng:
                    m = re.match(r"bytes=(\d+)-(\d*)", rng)
                    a = int(m.group(1))
                    b = int(m.group(2)) if m.group(2) else len(data) - 1
                    if a >= len(data):
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{len(data)}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    b = min(b, len(data) - 1)
                    if outer.max_conns and b - a > 0:  # 1 baytlık ön sorgu sayılmaz
                        with conn_lock:
                            if outer.open_conns >= outer.max_conns:
                                self.close_connection = True
                                return self._send(503, b"")  # bağlantı sınırı
                            outer.open_conns += 1
                            outer.peak_conns = max(getattr(outer, "peak_conns", 0), outer.open_conns)
                        try:
                            self.send_response(206)
                            self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
                            return self._body(path, data, a, b)
                        finally:
                            with conn_lock:
                                outer.open_conns -= 1
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
                else:
                    self.send_response(200)
                self._body(path, data, a, b)

            def _body(self, path, data, a, b):
                self.send_header("Content-Length", str(b - a + 1))
                if path in outer.cd:
                    self.send_header("Content-Disposition", outer.cd[path])
                self.end_headers()
                body = data[a:b + 1]
                drop = None
                if outer.drop_after is not None and outer.drop_budget > 0 and len(body) > outer.drop_after:
                    outer.drop_budget -= 1
                    drop = outer.drop_after
                try:
                    for i in range(0, len(body), 65536):
                        if drop is not None and i >= drop:
                            self.close_connection = True
                            return
                        self.wfile.write(body[i:i + 65536])
                        if outer.delay:
                            time.sleep(outer.delay)
                except OSError:
                    pass

            def _send(self, code, body):
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_port}"

    def url(self, path):
        return self.base + path

    def close(self):
        self.srv.shutdown()


class Item:
    def __init__(self, url, path, connections=8, **kw):
        self.url, self.path, self.headers = url, path, {}
        self.size, self.resumable, self.segments = None, True, []
        self.connections = connections
        self.extra = {}
        self.__dict__.update(kw)


def md5(b):
    return hashlib.md5(b).hexdigest()


def wait(task, timeout=60):
    end = time.time() + timeout
    while task.state not in ("completed", "error", "stopped") and time.time() < end:
        time.sleep(0.05)
    return task.state


def newdir():
    return tempfile.mkdtemp(dir=TMP)


# ---------------------------------------------------------------------------------------------- motor
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = FakeServer()
        cls.big = os.urandom(12 * 1024 * 1024 + 777)
        cls.s.files["/big.bin"] = cls.big

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def setUp(self):
        s = self.s
        s.range, s.delay, s.drop_after, s.drop_budget = True, 0.0, None, 0
        s.requests.clear()

    def run_item(self, it, lim=None, timeout=60):
        t = HttpTask(it, lim or SpeedLimiter(0))
        t.start()
        wait(t, timeout)
        return t

    def test_multi_connection_integrity(self):
        it = Item(self.s.url("/big.bin"), os.path.join(newdir(), "a.bin"))
        t = self.run_item(it)
        self.assertEqual(t.state, "completed", t.error)
        self.assertEqual(md5(open(it.path, "rb").read()), md5(self.big))
        self.assertFalse(os.path.exists(it.path + ".tdm"))

    def test_pause_resume_after_restart(self):
        self.s.delay = 0.01
        it = Item(self.s.url("/big.bin"), os.path.join(newdir(), "a.bin"))
        t = HttpTask(it, SpeedLimiter(3 * 1048576))
        t.start()
        time.sleep(1.5)
        t.stop()
        t.join(10)
        self.assertEqual(t.state, "stopped")
        done1 = t.downloaded()
        self.assertGreater(done1, 0)
        it.segments = json.loads(json.dumps(it.segments))  # diske yazılıp okunmuş gibi
        self.s.delay = 0
        t2 = HttpTask(it, SpeedLimiter(0))
        t2.start()
        time.sleep(0.05)
        self.assertGreaterEqual(t2.downloaded(), done1 - 64 * 1024, "devam sıfırdan başladı")
        wait(t2)
        self.assertEqual(md5(open(it.path, "rb").read()), md5(self.big))

    def test_server_without_range(self):
        self.s.range = False
        it = Item(self.s.url("/big.bin"), os.path.join(newdir(), "a.bin"))
        t = self.run_item(it)
        self.assertEqual(t.state, "completed", t.error)
        self.assertFalse(it.resumable)
        self.assertEqual(open(it.path, "rb").read(), self.big)

    def test_unknown_size_chunked(self):
        data = os.urandom(3 * 1024 * 1024)
        self.s.files["/chunk.bin"] = data
        self.s.chunked.add("/chunk.bin")
        it = Item(self.s.url("/chunk.bin"), os.path.join(newdir(), "c.bin"))
        t = self.run_item(it)
        self.assertEqual(t.state, "completed", t.error)
        self.assertEqual(open(it.path, "rb").read(), data)

    def test_zero_byte_file(self):
        self.s.files["/empty.txt"] = b""
        it = Item(self.s.url("/empty.txt"), os.path.join(newdir(), "e.txt"))
        t = self.run_item(it, timeout=20)
        self.assertEqual(t.state, "completed", t.error)
        self.assertEqual(os.path.getsize(it.path), 0)

    def test_tiny_file_single_segment(self):
        self.s.files["/tiny.txt"] = b"merhaba"
        it = Item(self.s.url("/tiny.txt"), os.path.join(newdir(), "t.txt"))
        t = self.run_item(it)
        self.assertEqual(t.state, "completed", t.error)
        self.assertEqual(open(it.path, "rb").read(), b"merhaba")

    def test_connection_drops_are_retried(self):
        self.s.drop_after, self.s.drop_budget = 200 * 1024, 6
        it = Item(self.s.url("/big.bin"), os.path.join(newdir(), "a.bin"))
        with mock.patch.object(engine, "MAX_RETRIES", 8):
            t = self.run_item(it, timeout=120)
        self.assertEqual(t.state, "completed", t.error)
        self.assertEqual(md5(open(it.path, "rb").read()), md5(self.big))

    def test_server_connection_limit_like_idm(self):
        # gofile gibi: sunucu aynı anda en fazla 4 bağlantıya izin veriyor, 32 bağlantı isteniyor. Fazla bağlantılar
        # indirmeyi düşürmeden çekilmeli, sınır öğrenilmeli, dosya eksiksiz inmeli.
        self.s.max_conns, self.s.delay = 4, 0.02
        try:
            it = Item(self.s.url("/big.bin"), os.path.join(newdir(), "lim.bin"), connections=32)
            with mock.patch.object(engine, "_retry_delay", lambda e, r: 0.05):
                t = self.run_item(it, timeout=120)
            self.assertEqual(t.state, "completed", t.error)
            self.assertEqual(md5(open(it.path, "rb").read()), md5(self.big))
            self.assertGreater(t.retired, 0, "fazla bağlantılar çekilmedi")
            lim = it.extra.get("server_conn_limit")
            self.assertTrue(lim and lim <= 4, lim)
        finally:
            self.s.max_conns, self.s.delay = 0, 0.0

    def test_connection_limit_grows_when_server_allows_more(self):
        # Sınır öğrenildikten sonra sunucu daha fazlasına izin verirse TurboDM bağlantı ekleyip bunu fark etmeli
        self.s.max_conns, self.s.delay, self.s.peak_conns = 4, 0.05, 0
        try:
            it = Item(self.s.url("/big.bin"), os.path.join(newdir(), "grow.bin"), connections=16)
            with mock.patch.object(engine, "_retry_delay", lambda e, r: 0.05), \
                    mock.patch.object(engine.HttpTask, "GROW_INTERVAL", 0.3):
                t = HttpTask(it, SpeedLimiter(0))
                t.start()
                end = time.time() + 30
                while not it.extra.get("server_conn_limit") and time.time() < end:
                    time.sleep(0.05)
                self.assertTrue(it.extra.get("server_conn_limit"), "sınır öğrenilmedi")
                self.s.max_conns = 8  # sunucu gevşedi
                wait(t, 120)
            self.assertEqual(t.state, "completed", t.error)
            self.assertEqual(md5(open(it.path, "rb").read()), md5(self.big))
            self.assertGreater(self.s.peak_conns, 4, "yeni bağlantı denenmedi")
            self.assertGreater(it.extra["server_conn_limit"], 4)
        finally:
            self.s.max_conns, self.s.delay = 0, 0.0

    def test_404_fails_fast_with_message(self):
        it = Item(self.s.url("/yok.bin"), os.path.join(newdir(), "y.bin"))
        t0 = time.time()
        t = self.run_item(it, timeout=30)
        self.assertEqual(t.state, "error")
        self.assertIn("404", t.error)
        self.assertLess(time.time() - t0, 10)

    def test_truncated_body_is_not_completed(self):
        data = os.urandom(500_000)
        self.s.files["/short.bin"] = data
        self.s.lie_length["/short.bin"] = 2_000_000
        it = Item(self.s.url("/short.bin"), os.path.join(newdir(), "s.bin"))
        with mock.patch.object(engine, "MAX_RETRIES", 1):
            t = self.run_item(it, timeout=30)
        self.assertEqual(t.state, "error")
        self.assertFalse(os.path.exists(it.path), "yarım dosya tamamlanmış gibi bırakıldı")

    def test_max_request_respected(self):
        it = Item(self.s.url("/big.bin"), os.path.join(newdir(), "a.bin"), max_request=1024 * 1024)
        t = self.run_item(it)
        self.assertEqual(t.state, "completed", t.error)
        sizes = []
        for _, rng in self.s.requests:
            m = re.match(r"bytes=(\d+)-(\d+)", rng or "")
            if m:
                sizes.append(int(m.group(2)) - int(m.group(1)) + 1)
        self.assertTrue(sizes)
        self.assertLessEqual(max(sizes), 1024 * 1024)
        self.assertEqual(md5(open(it.path, "rb").read()), md5(self.big))

    def test_speed_limit_global_and_per_item(self):
        data = os.urandom(4 * 1024 * 1024)
        self.s.files["/lim.bin"] = data
        it = Item(self.s.url("/lim.bin"), os.path.join(newdir(), "l.bin"))
        t0 = time.time()
        t = self.run_item(it, ChainLimiter(SpeedLimiter(0), SpeedLimiter(1024 * 1024)))
        dt = time.time() - t0
        self.assertEqual(t.state, "completed")
        self.assertGreater(dt, 2.5, "indirmeye özel sınır uygulanmadı")
        self.assertEqual(open(it.path, "rb").read(), data)

    def test_redirect_and_content_disposition_name(self):
        self.s.files["/real.bin"] = b"x" * 1000
        self.s.redirects["/go"] = "/real.bin"
        self.s.cd["/real.bin"] = "attachment; filename*=UTF-8''%C5%9Eark%C4%B1%20%E2%84%A2.mp3"
        info = probe(self.s.url("/go"))
        self.assertTrue(info["final_url"].endswith("/real.bin"))
        self.assertEqual(info["filename"], "Şarkı ™.mp3")

    def test_expired_redirect_is_refreshed(self):
        """Süreli imzalı adrese yönlendiren indirme: imzanın süresi dolunca asıl adresten yenilenip sürmeli."""
        self.s.files["/signed.bin"] = self.big
        state = {"n": 0}

        def target():
            state["n"] += 1
            return f"/signed.bin?sig={state['n']}"
        self.s.redirects["/dl"] = target
        # kısa istekler: imzanın süresi dolduktan sonra yeni istek açılsın (gerçek hayattaki gibi)
        it = Item(self.s.url("/dl"), os.path.join(newdir(), "s.bin"), max_request=256 * 1024)
        self.s.delay = 0.02
        t = HttpTask(it, SpeedLimiter(0))
        t.start()
        time.sleep(0.5)
        self.assertNotEqual(t.state, "completed", "test geçersiz: dosya imza süresi dolmadan bitti")
        self.s.forbidden.add("/signed.bin?sig=1")   # ilk imzanın süresi doldu
        wait(t, 120)
        self.s.forbidden.clear()
        self.assertEqual(t.state, "completed", t.error)
        self.assertGreaterEqual(state["n"], 2)
        self.assertEqual(md5(open(it.path, "rb").read()), md5(self.big))

    def test_not_enough_disk_space(self):
        it = Item(self.s.url("/big.bin"), os.path.join(newdir(), "a.bin"))
        fake = shutil._ntuple_diskusage(100, 99, 1000)
        with mock.patch.object(engine.shutil, "disk_usage", return_value=fake):
            t = self.run_item(it, timeout=20)
        self.assertEqual(t.state, "error")
        self.assertIn("boş alan", t.error)

    def test_disk_write_error_fails_fast_in_turkish(self):
        e = OSError(28, "No space left on device")
        self.assertTrue(engine._fatal(e))
        self.assertIn("boş alan", engine._err_text(e))
        e2 = PermissionError(13, "Permission denied", "C:\\x")
        self.assertIn("yazılamıyor", engine._err_text(e2))

    def test_stop_during_probe_and_immediate_restart_is_safe(self):
        self.s.delay = 0.02
        it = Item(self.s.url("/big.bin"), os.path.join(newdir(), "a.bin"))
        for _ in range(3):
            t = HttpTask(it, SpeedLimiter(0))
            t.start()
            time.sleep(0.4)
            t.stop()
            t.join(15)
            self.assertFalse(t.alive)
        self.s.delay = 0
        t = HttpTask(it, SpeedLimiter(0))
        t.start()
        wait(t)
        self.assertEqual(md5(open(it.path, "rb").read()), md5(self.big))


@unittest.skipUnless(FF, "ffmpeg yok")
class ConvertTests(unittest.TestCase):
    """İndirme bitince biçim dönüştürme (MKV / AVI / MP3)."""

    @classmethod
    def setUpClass(cls):
        cls.dir = newdir()
        cls.sample = os.path.join(cls.dir, "ornek.mp4")
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc=size=320x240:rate=25:duration=2", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=2", "-c:v", "mpeg4", "-c:a", "aac", "-shortest",
                        cls.sample], check=True, capture_output=True)
        with open(cls.sample, "rb") as f:
            cls.data = f.read()

    def fresh(self, name):
        p = os.path.join(newdir(), name)
        with open(p, "wb") as f:
            f.write(self.data)
        return p

    def test_formats(self):
        from turbodm import convert
        magic = {"mkv": b"\x1aE\xdf\xa3", "avi": b"RIFF", "mp3": (b"ID3", b"\xff\xfb", b"\xff\xf3")}
        for fmt, sig in magic.items():
            src = self.fresh("film.mp4")
            dst = convert.convert(FF, src, fmt)
            self.assertTrue(dst.endswith("." + fmt), dst)
            self.assertFalse(os.path.exists(src), "asıl dosya silinmedi")
            head = open(dst, "rb").read(4)
            sigs = sig if isinstance(sig, tuple) else (sig,)
            self.assertTrue(any(head.startswith(x) for x in sigs), (fmt, head))
            if fmt == "avi":
                self.assertIn(b"AVI ", open(dst, "rb").read(12))

    def test_failure_keeps_original(self):
        from turbodm import convert
        src = os.path.join(newdir(), "bozuk.mp4")
        with open(src, "wb") as f:
            f.write(b"bu bir video degil")
        with self.assertRaises(OSError):
            convert.convert(FF, src, "avi")
        self.assertTrue(os.path.exists(src))
        self.assertEqual(os.listdir(os.path.dirname(src)), ["bozuk.mp4"], "yarım dosya kaldı")

    def test_existing_target_not_overwritten(self):
        from turbodm import convert
        src = self.fresh("klip.mp4")
        other = os.path.splitext(src)[0] + ".mkv"
        with open(other, "wb") as f:
            f.write(b"kullanicinin dosyasi")
        dst = convert.convert(FF, src, "mkv")
        self.assertEqual(os.path.basename(dst), "klip (2).mkv")
        self.assertEqual(open(other, "rb").read(), b"kullanicinin dosyasi")

    def test_download_then_convert_via_manager(self):
        s = FakeServer()
        s.files["/video.mp4"] = self.data
        try:
            m = manager.Manager()
            it = m.add_http(s.url("/video.mp4"), os.path.join(newdir(), "video.mp4"), start=False)
            it.extra["convert"] = "mkv"
            m.start(it.id)
            end = time.time() + 60
            seen = set()
            while time.time() < end and it.status != "completed":
                m.tick()
                seen.add(it.status)
                time.sleep(0.05)
            self.assertEqual(it.status, "completed", it.description)
            self.assertIn("converting", seen)
            self.assertTrue(it.path.endswith(".mkv") and os.path.isfile(it.path))
            self.assertFalse(os.path.exists(os.path.splitext(it.path)[0] + ".mp4"))
            self.assertIn(("completed", it), m.events)
            if m.torrents:
                m.torrents.shutdown()
        finally:
            s.close()


class VideoHeaderTests(unittest.TestCase):
    def test_referer_and_origin_passed_to_ytdlp(self):
        h = {"Referer": "https://oynatici.example/embed/1", "Origin": "https://oynatici.example",
             "Cookie": "x=1", "User-Agent": "UA"}
        args = ytdlp._header_args("https://cdn.example/v/master.mpd", h)
        self.assertEqual(args, ["--referer", "https://oynatici.example/embed/1",
                                "--add-header", "Origin:https://oynatici.example"])
        self.assertEqual(ytdlp._header_args("https://www.youtube.com/watch?v=abcDEF12345", h), [])

    def test_dash_detection(self):
        from turbodm.gui import is_dash
        self.assertTrue(is_dash("https://cdn.example/a/manifest.mpd?token=1"))
        self.assertTrue(is_dash("https://cdn.example/play", "application/dash+xml; charset=utf-8"))
        self.assertFalse(is_dash("https://cdn.example/a/video.mp4", "video/mp4"))


class FilenameTests(unittest.TestCase):
    def test_sanitize(self):
        self.assertEqual(sanitize_filename('a<b>c:"d"/e\\f|g?h*.mp4'), "a_b_c__d__e_f_g_h_.mp4")
        self.assertEqual(sanitize_filename("CON.txt"), "_CON.txt")
        self.assertEqual(sanitize_filename("nul"), "_nul")
        self.assertEqual(sanitize_filename("  ..  "), "download")
        long = sanitize_filename("x" * 400 + ".mp4")
        self.assertLessEqual(len(long), engine.MAX_NAME)
        self.assertTrue(long.endswith(".mp4"))
        self.assertEqual(sanitize_filename("Şampiyonlar Ligi | Özet ™ 🎉.mp4"), "Şampiyonlar Ligi _ Özet ™ 🎉.mp4")

    def test_long_path_fits_windows_limit(self):
        folder = os.path.join(os.path.expanduser("~"), "Downloads", "TurboDM", "Video")
        name = sanitize_filename("Ç" * 500 + ".mp4")
        part = os.path.join(folder, os.path.splitext(name)[0] + ".f702.webm.tdm")
        self.assertLess(len(part), 260)


_TEST_KEY = None


def sign_manifest(m):
    """Test anahtarıyla latest.json imzalar (gerçek anahtar yalnızca geliştiricinin bilgisayarında)."""
    global _TEST_KEY
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from turbodm import updater
    _TEST_KEY = _TEST_KEY or Ed25519PrivateKey.generate()
    m["sig"] = base64.b64encode(_TEST_KEY.sign(updater.signed_payload(m))).decode()
    return base64.b64encode(_TEST_KEY.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


class UpdateSecurityTests(unittest.TestCase):
    def setUp(self):
        from turbodm import updater
        self.u = updater
        self.m = {"version": "9.9.9", "build": "b", "url": updater.ALLOWED_DOWNLOAD[0] + "v9.9.9/TurboDM-Setup-9.9.9.exe",
                  "sha256": "a" * 64, "size": 1, "notes": "• not"}

    def test_signed_manifest_accepted(self):
        pub = sign_manifest(self.m)
        self.u.verify_manifest(self.m, keys=(pub,))

    def test_unsigned_rejected(self):
        with self.assertRaisesRegex(ValueError, "imzasız"):
            self.u.verify_manifest(self.m)

    def test_tampered_manifest_rejected(self):
        pub = sign_manifest(self.m)
        self.m["sha256"] = "b" * 64  # saldırgan kendi dosyasının özetini koydu
        with self.assertRaisesRegex(ValueError, "imzası doğrulanamadı"):
            self.u.verify_manifest(self.m, keys=(pub,))

    def test_foreign_key_rejected(self):
        sign_manifest(self.m)  # test anahtarı programdaki gerçek açık anahtar değil
        with self.assertRaisesRegex(ValueError, "imzası doğrulanamadı"):
            self.u.verify_manifest(self.m)

    def test_foreign_download_url_rejected(self):
        self.m["url"] = "https://kotu-site.example/TurboDM-Setup.exe"
        pub = sign_manifest(self.m)
        with self.assertRaisesRegex(ValueError, "resmi sürüm"):
            self.u.verify_manifest(self.m, keys=(pub,))
        with self.assertRaisesRegex(ValueError, "resmi sürüm"):
            self.u.download({"url": self.m["url"], "sha256": "a" * 64})

    def test_real_public_key_matches_local_signing_key(self):
        # Geliştirici bilgisayarında: programdaki açık anahtar, imzalama anahtarıyla eşleşmeli
        key_file = os.path.join(ROOT, "keys", "update_signing.key")
        if not os.path.isfile(key_file):
            self.skipTest("imzalama anahtarı bu bilgisayarda yok")
        sys.path.insert(0, os.path.join(ROOT, "installer"))
        import sign_update
        self.assertIn(sign_update.public_b64(sign_update.load_key()), self.u.PUBLIC_KEYS)


class LocaleTests(unittest.TestCase):
    """Çeviriler: koddaki her _t() metni her dilde var mı, yer tutucular ({0}, {1:.2f}…) aynı mı."""

    def test_all_languages_complete_and_placeholders_match(self):
        import string
        sys.path.insert(0, os.path.join(ROOT, "installer"))
        import i18n_wrap
        from turbodm import i18n
        files = [os.path.join(ROOT, "main.py")] + [os.path.join(ROOT, "turbodm", f) for f in os.listdir(
            os.path.join(ROOT, "turbodm")) if f.endswith(".py")]
        keys = set(i18n_wrap.keys(files))
        self.assertGreater(len(keys), 300)
        fields = lambda s: sorted((f, spec) for _, f, spec, _ in string.Formatter().parse(s) if f is not None)  # noqa: E731
        for code in i18n.LANGUAGES:
            if code == "tr":
                continue
            with open(os.path.join(ROOT, "turbodm", "locale", code + ".json"), encoding="utf-8") as f:
                table = json.load(f)
            missing = sorted(keys - set(table))
            self.assertEqual(missing, [], f"{code}: çevirisi eksik metinler")
            for k in keys:
                self.assertEqual(fields(k), fields(table[k]), f"{code}: yer tutucu uyuşmuyor: {k!r}")

    def test_switching_language_translates(self):
        from turbodm import convert, i18n, manager, torrent
        try:
            i18n.set_language("fr")  # modül tabloları da anında yeni dilde (yeniden başlatmadan)
            self.assertEqual(manager.CATEGORIES["music"][0], "Musique")
            self.assertNotEqual(torrent.STATE_TEXT["downloading"], "İndiriliyor")
            self.assertTrue(convert.FORMATS["mp3"][0].startswith("MP3"))
            self.assertEqual(i18n.resolve("auto"), i18n.system_language())  # varsayılan: Windows'un dili
            self.assertIn(i18n.resolve(None), i18n.LANGUAGES)
            i18n.set_language("de")
            self.assertEqual(i18n._t("İndirmeyi Başlat"), "Download starten")
            i18n.set_language("ar")
            self.assertTrue(i18n.is_rtl())
            self.assertEqual(i18n._t("bu metin çevrilmemiş"), "bu metin çevrilmemiş")  # yoksa Türkçe kalır
        finally:
            i18n.set_language("tr")

    def test_installer_language_saved_without_touching_other_settings(self):
        # kurulumda seçilen dil: TurboDM.exe --set-language <kod> (APPDATA testte sahte klasör)
        import main
        from turbodm import i18n
        path = os.path.join(os.environ["APPDATA"], "TurboDM", "settings.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"max_connections": 5}, f)
        self.assertEqual(main._tool_mode(["--set-language", "fr"]), 0)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"max_connections": 5, "language": "fr"})
        self.assertEqual(main._tool_mode(["--set-language", "xx"]), 1)  # bilinmeyen dil yazılmaz
        self.assertEqual(i18n.language(), "tr")  # çalışan programın dili değişmez (yeniden açınca geçerli)
        os.remove(path)


class ExtensionTests(unittest.TestCase):
    def test_page_url_is_reduced_to_single_video(self):
        w = "https://www.youtube.com/watch?v=abcDEF12345"
        for u in ("https://www.youtube.com/watch?v=abcDEF12345&list=PL1&t=42s",
                  "https://m.youtube.com/shorts/abcDEF12345", "https://youtu.be/abcDEF12345?si=x",
                  "https://www.youtube-nocookie.com/embed/abcDEF12345"):
            self.assertEqual(ytdlp.canonical_url(u), w, u)
        for u in ("https://vimeo.com/123456", "https://www.youtube.com/feed/trending", "https://site.com/v?v=1"):
            self.assertEqual(ytdlp.canonical_url(u), u)

    def test_extension_locales_complete(self):
        # mağazada Türkçe/İngilizce sayfa: manifest'teki her __MSG_x__ her dilde tanımlı olmalı
        folder = os.path.join(ROOT, "browser_extension")
        man = json.load(open(os.path.join(folder, "manifest.json"), encoding="utf-8"))
        keys = set(re.findall(r"__MSG_(\w+)__", json.dumps(man)))
        self.assertTrue(keys)
        # arayüz metinleri: kodda M("anahtar") ve popup.html'de data-i18n="anahtar"
        for name in ("background.js", "content.js", "popup.js", "popup.html"):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                text = f.read()
            keys |= set(re.findall(r'\bM\("(\w+)"\)', text)) | set(re.findall(r'data-i18n="(\w+)"', text))
        self.assertIn("btnDownload", keys)
        for lang in ("tr", "en", "de", "fr", "es", "ar", "it"):
            msgs = json.load(open(os.path.join(folder, "_locales", lang, "messages.json"), encoding="utf-8"))
            self.assertFalse(keys - set(msgs), lang)
        self.assertTrue(os.path.isdir(os.path.join(folder, "_locales", man["default_locale"])))

    def test_https_uses_windows_certificate_verification(self):
        # sertifikalar Windows'un doğrulamasıyla denetlenir (yeni kök sertifikalar gerektiğinde indirilir);
        # Python'un kendi doğrulaması yeni Let's Encrypt zincirinde "certificate has expired" diyordu
        import ssl
        from turbodm import engine
        self.assertEqual(type(engine.SSL_CONTEXT).__module__.split(".")[0], "truststore")
        self.assertEqual(engine.SSL_CONTEXT.verify_mode, ssl.CERT_REQUIRED)  # doğrulama kapatılmadı
        self.assertTrue(engine.SSL_CONTEXT.check_hostname)

    def test_extension_button_only_on_visible_video(self):
        # Gerçek tarayıcıda (Edge, görünmez): "Bu videoyu indir" düğmesi yalnızca görünen videoda olmalı.
        #  * hikâye sayfaları (Instagram vb.): yanlardaki kesilmiş ve şeffaf videolara düğme konmaz
        #  * body'si overflow ayarlı ve yüksekliği 0 ölçülen sayfalar (YouTube): ana videoya düğme konur
        import subprocess
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        edge = next((p for p in (os.path.join(os.environ.get(b, ""), "Microsoft", "Edge", "Application", "msedge.exe")
                                 for b in ("ProgramFiles(x86)", "ProgramFiles")) if os.path.isfile(p)), None)
        if not edge:
            self.skipTest("Microsoft Edge yok")
        results = {}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
                name, _, value = body.partition("=")
                results[name] = value
                self.send_response(204)
                self.end_headers()

        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        ext = "file:///" + os.path.join(ROOT, "browser_extension").replace("\\", "/") + "/"
        stub = ("window.__errs=0;addEventListener('error',()=>__errs++);addEventListener('unhandledrejection',()=>__errs++);"
                "window.chrome={i18n:{getMessage:k=>k},runtime:{id:'test',lastError:null,onMessage:{addListener(){}},"
                "sendMessage(m,cb){setTimeout(()=>cb(m.type==='tdm-list'?[{url:'x',kind:'hls',label:'x'}]:{ok:true}),5)}}};")
        pages = {
            "hikaye": '<div style="position:absolute;left:400px;top:50px;width:500px;height:700px;overflow:hidden">'
                      '<div style="display:flex;transform:translateX(-500px)">' +
                      '<video style="flex:0 0 500px;height:700px"></video>' * 3 + '</div></div>'
                      '<video style="position:absolute;left:1000px;top:100px;width:300px;height:300px;opacity:0"></video>',
            "youtube": '<style>body{overflow:auto scroll;height:0}</style><div style="overflow:hidden;width:1080px;'
                       'height:608px;margin:60px 16px"><video style="width:1080px;height:608px"></video></div>',
            # eklenti güncellendi: eski kopya bağını kaybeder (runtime.id kalkar) → düğmeleri kaldırıp sessizce durmalı
            "yetim": '<video style="width:1000px;height:560px"></video>'
                     '<script>setTimeout(()=>{delete chrome.runtime.id;chrome.i18n.getMessage=()=>{throw new Error('
                     '"Extension context invalidated.")}},700)</script>',
            # × : düğme bu sayfada gizlenir (sayfa yenilenince geri gelir)
            "kapat": '<video style="width:1000px;height:560px"></video>'
                     '<script>setTimeout(()=>document.querySelector(".tdm-close").click(),900)</script>',
        }
        procs = []
        try:
            for name, body in pages.items():
                html = (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{ext}content.css">'
                        f'<script>{stub}</script></head><body style="margin:0">{body}<script src="{ext}content.js"></script>'
                        f'<script>setTimeout(()=>{{const b=[...document.querySelectorAll(".tdm-grab")].filter(e=>'
                        f'e.style.display==="block");fetch("http://127.0.0.1:{srv.server_port}/",{{method:"POST",'
                        f'mode:"no-cors",body:"{name}="+b.length+"@"+b.map(e=>parseInt(e.style.left)).join(",")+"!"+__errs'
                        f'+"~"+b.filter(e=>e.classList.contains("tdm-idle")).length}})}},4200)'
                        f'</script></body></html>')
                path = os.path.join(TMP, f"eklenti_{name}.html")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
                procs.append(subprocess.Popen(
                    [edge, "--headless=new", f"--user-data-dir={os.path.join(TMP, 'edge_' + name)}",
                     "--allow-file-access-from-files", "--window-size=1400,900", "file:///" + path.replace("\\", "/")],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            end = time.time() + 45
            while len(results) < len(pages) and time.time() < end:
                time.sleep(0.2)
        finally:
            for p in procs:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
            srv.shutdown()
        count, _, lefts = results.get("hikaye", "0@").partition("@")
        self.assertEqual(count, "1", results)  # yalnızca ortadaki video
        self.assertTrue(400 < int(lefts.split("!")[0]) < 900, results)
        count, _, lefts = results.get("youtube", "0@").partition("@")
        self.assertEqual(count, "1", results)  # YouTube'da düğme kaybolmamalı
        self.assertTrue(16 < int(lefts.split("!")[0]) < 1096, results)
        self.assertEqual(results.get("yetim"), "0@!0~0", results)  # düğme kaldırıldı, hiç hata fırlatılmadı
        self.assertEqual(results.get("kapat"), "0@!0~0", results)  # × ile gizlendi
        self.assertTrue(results.get("youtube", "").endswith("~1"), results)  # fare kıpırdamayınca soldu

    def test_extension_popup_hides_empty_media_section(self):
        # "Bu sayfadaki medyalar" yalnızca sayfada akış bulunduysa görünür (boş "Yok" yazısı gösterilmez)
        folder = os.path.join(ROOT, "browser_extension")
        with open(os.path.join(folder, "popup.html"), encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(folder, "popup.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertRegex(html, r'id="media"[^>]*display:\s*none')
        self.assertIn('if (!list || !list.length) return;', js)
        self.assertNotIn("popupNone", html + js)
        self.assertIn("prefers-color-scheme: dark", html)  # tarayıcının koyu/açık moduna uyar
        # mağaza ekran görüntüsü sahnesi: sahte ortamda eklenti kimliği olmalı (yoksa eklenti "bağı koptu"
        # sanıp durur ve görüntüde düğme/menü çıkmaz)
        with open(os.path.join(ROOT, "store", "demo", "video.html"), encoding="utf-8") as f:
            self.assertRegex(f.read(), r"runtime:\s*\{\s*id:")

    def test_extension_leaves_form_post_downloads_to_browser(self):
        # form gönderimiyle (POST) gelen dosya (ör. altyazı sitelerinin "indir" düğmesi) TurboDM'e verilmez:
        # TurboDM aynı adresi form verisi olmadan isterse dosya yerine sayfa alır ("ind" adlı anlamsız dosya)
        # Eklentinin gerçek kodu sahte tarayıcı olaylarıyla çalıştırılır (deno): form gönderimi + indirme başlangıcı
        import subprocess
        deno = os.path.join(ROOT, "vendor", "deno", "deno.exe")
        if not os.path.isfile(deno):
            self.skipTest("deno yok")
        r = subprocess.run([deno, "run", "--allow-read", os.path.join(ROOT, "tests", "extension_background_sim.js"),
                            os.path.join(ROOT, "browser_extension", "background.js")],
                           capture_output=True, text=True, encoding="utf-8", timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        res = json.loads(r.stdout[r.stdout.index("{"):])
        self.assertFalse(res["form_post"]["turbodm_e_gitti"], res)   # form indirmesi tarayıcıda kalır
        self.assertFalse(res["form_post"]["duraklatildi"], res)
        self.assertTrue(res["normal_get"]["turbodm_e_gitti"], res)   # normal indirme yine TurboDM'e gider
        self.assertTrue(res["normal_get"]["tarayicida_iptal"], res)

    def test_extension_tab_calls_tolerate_closed_tabs(self):
        # sekme kapanınca rozet çağrıları "No tab with id" hatası fırlatır: hepsi .catch ile yakalanmalı
        with open(os.path.join(ROOT, "browser_extension", "background.js"), encoding="utf-8") as f:
            text = f.read()
        calls = re.findall(r"chrome\.(?:action\.setBadge\w+|tabs\.sendMessage)\([^;]*;", text)
        self.assertTrue(calls)
        for c in calls:
            self.assertIn(".catch(", c, c)

    def test_extension_is_site_agnostic(self):
        # Eklenti hiçbir siteye özel kod içermez: sayfa adresini TurboDM'e verir, videoyu uygulama çözer
        folder = os.path.join(ROOT, "browser_extension")
        for name in os.listdir(folder):
            if not name.endswith((".js", ".json", ".html", ".css")):
                continue
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                text = f.read().lower()
            for word in ("youtube", "youtu.be", "googlevideo", "yt-navigate", "ytd-"):
                self.assertNotIn(word, text, f"{name}: siteye özel '{word}'")


# ---------------------------------------------------------------------------------------------- .torrent bağlantıları
class TorrentLinkTests(unittest.TestCase):
    TORRENT = b"d8:announce20:http://t.example/ann4:infod6:lengthi5e4:name5:a.txt12:piece lengthi16384e6:pieces20:" \
              + b"x" * 20 + b"ee"

    @classmethod
    def setUpClass(cls):
        cls.s = FakeServer()
        cls.s.files["/f/abc.torrent"] = cls.TORRENT
        cls.s.files["/dl.php"] = cls.TORRENT
        cls.s.cd["/dl.php"] = 'attachment; filename="film.torrent"'
        # dosyadrive gibi: .torrent adresi, tarayıcı dışından istenince indirme sayfası döner
        cls.s.files["/page/x.torrent"] = b"<!DOCTYPE html><html><body>Download</body></html>"

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def test_detect(self):
        self.assertTrue(engine.looks_like_torrent("https://a/b/c.torrent?x=1"))
        self.assertTrue(engine.looks_like_torrent("https://a/dl.php", {"filename": "film.torrent"}))
        self.assertTrue(engine.looks_like_torrent("https://a/dl", {"content_type": "application/x-bittorrent"}))
        self.assertFalse(engine.looks_like_torrent("https://a/film.mp4", {"filename": "film.mp4"}))

    def test_fetch_valid(self):
        self.assertEqual(engine.fetch_torrent(self.s.url("/f/abc.torrent")), self.TORRENT)
        info = engine.probe(self.s.url("/dl.php"))
        self.assertTrue(engine.looks_like_torrent(self.s.url("/dl.php"), info))

    def test_fetch_html_page_rejected(self):
        with self.assertRaises(ValueError) as cm:
            engine.fetch_torrent(self.s.url("/page/x.torrent"))
        self.assertIn("web sayfası", str(cm.exception))


# ---------------------------------------------------------------------------------------------- yt-dlp hızlı mod
@unittest.skipUnless(FF, "ffmpeg yok")
class FastModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = FakeServer()
        d = newdir()
        run = lambda *a: subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *a], check=True, cwd=d)
        run("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=30", "-c:v", "libopenh264", "-b:v", "4M", "v.mp4")
        run("-f", "lavfi", "-i", "sine=duration=30", "-c:a", "aac", "a.m4a")
        for n in ("v.mp4", "a.m4a"):
            cls.s.files["/" + n] = open(os.path.join(d, n), "rb").read()
        cls.s.delay = 0.002

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def fmts(self, vsig="ok"):
        S = self.s.files
        return [{"format_id": "137", "url": self.s.url(f"/v.mp4?sig={vsig}"), "http_headers": {},
                 "filesize": len(S["/v.mp4"]), "ext": "mp4", "vcodec": "avc1", "protocol": "https"},
                {"format_id": "140", "url": self.s.url("/a.m4a?sig=ok"), "http_headers": {},
                 "filesize": len(S["/a.m4a"]), "ext": "m4a", "vcodec": "none", "protocol": "https"}]

    def item(self, name="Video ™ ドルビー.mp4"):
        it = Item("https://www.youtube.com/watch?v=T", os.path.join(newdir(), name))
        it.extra = {"format": "137+140", "ext": "mp4", "cookies": [], "size": 0}
        return it

    def assert_playable(self, path):
        r = subprocess.run([FF, "-hide_banner", "-v", "error", "-i", path, "-f", "null", "-"], capture_output=True, text=True)
        self.assertEqual(r.stderr.strip(), "", "birleşen dosyada çözme hatası")
        info = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stderr
        self.assertIn("Video: h264", info)
        self.assertIn("Audio: aac", info)

    def test_download_merge(self):
        it = self.item()
        t = ytdlp.YtdlpTask(it, SpeedLimiter(0), FF)
        t._resolve = self.fmts
        t.start()
        self.assertEqual(wait(t, 120), "completed", t.error)
        self.assert_playable(it.path)
        self.assertEqual(ytdlp.partial_files(it.path), [])

    def test_resume_after_restart_with_done_part(self):
        it = self.item()
        t = ytdlp.YtdlpTask(it, SpeedLimiter(1024 * 1024), FF)
        t._resolve = self.fmts
        t.start()
        end = time.time() + 30
        while not it.extra.get("parts", {}).get("140", {}).get("done") and time.time() < end:
            time.sleep(0.1)
        t.stop()
        t.join(30)
        it.extra = json.loads(json.dumps(it.extra))
        t = ytdlp.YtdlpTask(it, SpeedLimiter(512 * 1024), FF)
        t._resolve = self.fmts
        t.start()
        time.sleep(1)
        t.bar_data(), t.connections_snapshot(), t.downloaded()  # çökmemeli
        t.stop()
        t.join(30)
        self.assertEqual(t.state, "stopped")
        t = ytdlp.YtdlpTask(it, SpeedLimiter(0), FF)
        t._resolve = self.fmts
        t.start()
        self.assertEqual(wait(t, 120), "completed", t.error)
        self.assert_playable(it.path)

    def test_expired_url_refresh(self):
        it = self.item()
        calls = {"n": 0}

        def res():
            calls["n"] += 1
            return self.fmts("BOZUK" if calls["n"] == 1 else "ok")
        self.s.forbidden.add("/v.mp4?sig=BOZUK")
        t = ytdlp.YtdlpTask(it, SpeedLimiter(0), FF)
        t._resolve = res
        t.start()
        self.assertEqual(wait(t, 120), "completed", t.error)
        self.assertEqual(calls["n"], 2)

    def test_resolve_failure_leaves_no_orphans(self):
        it = self.item()
        calls = {"n": 0}

        def res():
            calls["n"] += 1
            if calls["n"] == 1:
                return self.fmts("BOZUK")
            raise RuntimeError("YouTube giriş doğrulaması istiyor")
        self.s.forbidden.add("/v.mp4?sig=BOZUK")
        t = ytdlp.YtdlpTask(it, SpeedLimiter(1024 * 1024), FF)
        t._resolve = res
        t.start()
        self.assertEqual(wait(t, 60), "error")
        time.sleep(0.3)
        self.assertFalse(any(getattr(x, "alive", False) for _, x in t.parts))
        self.assertIn("parts", it.extra)

    def test_prefetched_streams_skip_ytdlp(self):
        it = self.item()
        it.extra["streams"], it.extra["streams_t"] = self.fmts(), time.time()
        t = ytdlp.YtdlpTask(it, SpeedLimiter(0), FF)
        with mock.patch.object(ytdlp.subprocess, "run", wraps=subprocess.run) as run:
            t.start()
            self.assertEqual(wait(t, 120), "completed", t.error)
            self.assertFalse(any("yt-dlp" in str(c.args[0][0]) for c in run.call_args_list))

    def test_existing_output_is_recognised(self):
        it = self.item("Var.mp4")
        open(it.path, "wb").write(b"tamam")
        t = ytdlp.YtdlpTask(it, SpeedLimiter(0), FF)
        t._resolve = self.fmts
        t.start()
        self.assertEqual(wait(t, 10), "completed")
        self.assertEqual(t.mode, "done")

    def test_partial_files_is_strict(self):
        d = newdir()
        names = ["M.mp4", "M.f137.mp4", "M.f137.mp4.tdm", "M.f251-drc.webm.part", "M.mp4.part", "M.mp4.ytdl",
                 "M.temp.mp4", "M.2023.1080p.mkv", "M.2023.1080p.mkv.tdm", "M.final.mp4", "M.mkv", "M (1).f137.mp4"]
        for n in names:
            open(os.path.join(d, n), "w").close()
        got = sorted(os.path.basename(p) for p in ytdlp.partial_files(os.path.join(d, "M.mp4")))
        self.assertEqual(got, sorted(["M.f137.mp4", "M.f137.mp4.tdm", "M.f251-drc.webm.part", "M.mp4.part",
                                      "M.mp4.ytdl", "M.temp.mp4"]))


# ---------------------------------------------------------------------------------------------- HLS
class HlsTests(unittest.TestCase):
    def test_aes_master_audio_byterange_live(self):
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        s = FakeServer()
        key, n = os.urandom(16), 12
        V = [os.urandom(50_000 + i) for i in range(n)]
        A = [os.urandom(9_000 + i) for i in range(n)]

        def enc(d, seq):
            pad = 16 - len(d) % 16
            e = Cipher(algorithms.AES(key), modes.CBC(seq.to_bytes(16, "big"))).encryptor()
            return e.update(d + bytes([pad]) * pad) + e.finalize()
        s.files["/m.m3u8"] = (b'#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="a",DEFAULT=YES,URI="a.m3u8"\n'
                              b'#EXT-X-STREAM-INF:BANDWIDTH=900000,RESOLUTION=640x360,AUDIO="a"\nlo.m3u8\n'
                              b'#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1280x720,AUDIO="a"\nhi.m3u8\n')
        s.files["/hi.m3u8"] = ("#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:3\n#EXT-X-KEY:METHOD=AES-128,URI=\"k.bin\"\n"
                               + "".join(f"#EXTINF:4,\nv{i}.ts\n" for i in range(n)) + "#EXT-X-ENDLIST\n").encode()
        s.files["/a.m3u8"] = ("#EXTM3U\n" + "".join(f"#EXTINF:4,\na{i}.aac\n" for i in range(n)) + "#EXT-X-ENDLIST\n").encode()
        s.files["/live.m3u8"] = b"#EXTM3U\n#EXTINF:4,\nx.ts\n"
        s.files["/k.bin"] = key
        for i in range(n):
            s.files[f"/v{i}.ts"] = enc(V[i], 3 + i)
            s.files[f"/a{i}.aac"] = A[i]
        try:
            info = hls.inspect(s.url("/m.m3u8"))
            v = info["variants"][0]
            self.assertEqual(v["resolution"], "1280x720")
            it = Item(s.url("/m.m3u8"), os.path.join(newdir(), "film.mp4"), connections=4)
            it.extra = {"media_url": v["url"], "audio_url": v["audio_url"], "done": [], "bytes": 0}
            t = hls.HlsTask(it, SpeedLimiter(0), None)  # ffmpeg olmadan: ses ayrı dosyaya
            t.start()
            self.assertEqual(wait(t), "completed", t.error)
            self.assertEqual(open(it.path, "rb").read(), b"".join(V))
            it2 = Item(s.url("/live.m3u8"), os.path.join(newdir(), "c.mp4"))
            it2.extra = {"media_url": s.url("/live.m3u8"), "audio_url": None, "done": [], "bytes": 0}
            t2 = hls.HlsTask(it2, SpeedLimiter(0), None)
            t2.start()
            self.assertEqual(wait(t2), "error")
            self.assertIn("Canlı", t2.error)
        finally:
            s.close()


# ---------------------------------------------------------------------------------------------- FTP
try:
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import ThreadedFTPServer
    HAVE_FTP = True
except ImportError:
    HAVE_FTP = False


@unittest.skipUnless(HAVE_FTP, "pyftpdlib yok")
class FtpTests(unittest.TestCase):
    def test_ftp_multi_resume_and_missing(self):
        import logging
        logging.getLogger("pyftpdlib").setLevel(logging.ERROR)
        root = newdir()
        data = os.urandom(5 * 1024 * 1024 + 3)
        open(os.path.join(root, "dosya adı.iso"), "wb").write(data)
        a = DummyAuthorizer()
        a.add_user("ali", "s3cr3t", root)
        FTPHandler.authorizer = a
        srv = ThreadedFTPServer(("127.0.0.1", 0), FTPHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            url = f"ftp://ali:s3cr3t@127.0.0.1:{srv.address[1]}/dosya%20ad%C4%B1.iso"
            it = Item(url, os.path.join(newdir(), "f.iso"), connections=4)
            t = HttpTask(it, SpeedLimiter(2 * 1048576))
            t.start()
            time.sleep(1.2)
            t.stop()
            t.join(15)
            t = HttpTask(it, SpeedLimiter(0))
            t.start()
            self.assertEqual(wait(t), "completed", t.error)
            self.assertEqual(open(it.path, "rb").read(), data)
            it2 = Item(url.replace("dosya%20ad%C4%B1", "yok"), os.path.join(newdir(), "y.iso"))
            t2 = HttpTask(it2, SpeedLimiter(0))
            t2.start()
            self.assertEqual(wait(t2, 30), "error")
        finally:
            srv.close_all()


# ---------------------------------------------------------------------------------------------- yönetici
class ManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = FakeServer()
        cls.data = os.urandom(3 * 1024 * 1024)
        for i in range(6):
            cls.s.files[f"/f{i}.bin"] = cls.data
        manager.DEFAULT_SETTINGS.update(download_root=os.path.join(TMP, "dl"), torrent_port=6880 + os.getpid() % 100)

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def mgr(self):
        m = manager.Manager()
        self.addCleanup(lambda: m.torrents and m.torrents.shutdown())
        return m

    def tick_until(self, m, cond, timeout=60):
        end = time.time() + timeout
        while time.time() < end and not cond():
            m.tick()
            time.sleep(0.05)
        return cond()

    def test_corrupt_list_recovers_from_backup(self):
        m = self.mgr()
        it = m.add_http(self.s.url("/f0.bin"), os.path.join(newdir(), "x.bin"), start=False)
        m.save()
        m.save()  # .bak = önceki sağlam sürüm
        p = os.path.join(manager.APP_DIR, "downloads.json")
        open(p, "w").write('{"yarım": ')  # bozuk
        m2 = self.mgr()
        self.assertIn(it.id, m2.items, "liste bozulunca kayboldu")
        self.assertTrue([f for f in os.listdir(manager.APP_DIR) if ".bozuk-" in f], "bozuk dosya kenara alınmadı")

    def test_queue_respects_max_concurrent(self):
        m = self.mgr()
        m.settings["max_concurrent"] = 2
        self.s.delay = 0.01
        items = [m.add_http(self.s.url(f"/f{i}.bin"), os.path.join(newdir(), f"q{i}.bin"), start=False)
                 for i in range(5)]
        m.start_queue()
        peak = 0
        end = time.time() + 120
        while time.time() < end and not all(i.status == "completed" for i in items):
            m.tick()
            peak = max(peak, sum(1 for i in items if i.status in ("downloading", "connecting")))
            time.sleep(0.05)
        self.s.delay = 0
        self.assertTrue(all(i.status == "completed" for i in items))
        self.assertLessEqual(peak, 2)

    def test_quick_pause_resume_with_limit_keeps_file_intact(self):
        m = self.mgr()
        m.settings["speed_limit_kb"] = 400
        m.apply_settings()
        it = m.add_http(self.s.url("/f1.bin"), os.path.join(newdir(), "p.bin"), start=True)
        self.tick_until(m, lambda: False, 2)
        m.stop(it.id)
        self.tick_until(m, lambda: False, 0.3)
        m.start(it.id)
        m.settings["speed_limit_kb"] = 0
        m.apply_settings()
        self.assertTrue(self.tick_until(m, lambda: it.status == "completed", 60), it.error)
        self.assertEqual(open(it.path, "rb").read(), self.data)

    def test_same_name_twice_gets_unique_paths(self):
        m = self.mgr()
        d = newdir()
        a = m.add_http(self.s.url("/f2.bin"), os.path.join(d, "ayni.bin"), start=False)
        b = m.add_http(self.s.url("/f3.bin"), os.path.join(d, "ayni.bin"), start=False)
        self.assertNotEqual(a.path, b.path)

    def test_remove_with_files(self):
        m = self.mgr()
        it = m.add_http(self.s.url("/f4.bin"), os.path.join(newdir(), "r.bin"), start=True)
        self.assertTrue(self.tick_until(m, lambda: it.status == "completed"))
        m.remove(it.id, delete_file=True)
        end = time.time() + 10
        while os.path.exists(it.path) and time.time() < end:
            time.sleep(0.1)
        self.assertFalse(os.path.exists(it.path))

    def test_update_restart_resumes_only_active_downloads(self):
        m = manager.Manager()  # shutdown torrent motorunu da kapatır
        m.settings["speed_limit_kb"] = 300
        m.apply_settings()
        d = newdir()
        run = m.add_http(self.s.url("/f0.bin"), os.path.join(d, "u1.bin"), start=True)
        idle = m.add_http(self.s.url("/f1.bin"), os.path.join(d, "u2.bin"), start=False)
        self.assertTrue(self.tick_until(m, lambda: run.status == "downloading" and run.done_bytes > 0, 15))
        m.shutdown()  # kurulum programının --quit ile kapatması
        m2 = self.mgr()
        m2.settings["speed_limit_kb"] = 0
        m2.apply_settings()
        m2.resume_interrupted()  # TurboDM.exe --tray --resume
        self.assertIn(m2.items[run.id].status, ("downloading", "connecting"))
        self.assertNotIn(m2.items[idle.id].status, ("downloading", "connecting"), "durdurulmuş indirme başlamamalı")
        self.assertTrue(self.tick_until(m2, lambda: m2.items[run.id].status == "completed"), m2.items[run.id].error)
        self.assertEqual(open(run.path, "rb").read(), self.data)
        self.assertNotIn("resume_after_restart", m2.items[run.id].extra)

    def test_torrent_upload_auto_limit(self):
        m = self.mgr()
        self.assertEqual(m.upload_limit(), 0, "torrent inmiyorken sınır olmamalı")
        t = manager.DownloadItem(kind="torrent", path=newdir())
        m.items[t.id] = t
        t.status, t.speed = "downloading", 0
        self.assertEqual(m.upload_limit(), m.AUTO_UL_MIN)
        t.speed = 20 * 1024 * 1024  # 20 MB/s indirirken
        self.assertEqual(m.upload_limit(), int(20 * 1024 * 1024 * 0.08 + 100 * 1024))
        t.speed = 500 * 1024 * 1024
        self.assertEqual(m.upload_limit(), m.AUTO_UL_MAX)
        m.settings["torrent_upload_kb"] = 300  # elle verilen sınır her zaman geçerli
        self.assertEqual(m.upload_limit(), 300 * 1024)
        m.settings.update(torrent_upload_kb=0, torrent_upload_auto=False)
        self.assertEqual(m.upload_limit(), 0)
        t.status = "seeding"
        m.settings["torrent_upload_auto"] = True
        self.assertEqual(m.upload_limit(), 0, "yalnızca paylaşımda sınır olmamalı")
        del m.items[t.id]

    def test_default_torrent_port_is_randomised_once(self):
        old = dict(manager.DEFAULT_SETTINGS)
        try:
            manager.DEFAULT_SETTINGS.update(torrent_port=6881, torrent_port_random=False)
            self._drop_settings()
            m = self.mgr()
            port = m.settings["torrent_port"]
            self.assertTrue(49160 <= port <= 65000, port)
            m.save()
            self.assertEqual(self.mgr().settings["torrent_port"], port, "her açılışta değişmemeli")
        finally:
            manager.DEFAULT_SETTINGS.clear()
            manager.DEFAULT_SETTINGS.update(old)
            self._drop_settings()

    @staticmethod
    def _drop_settings():
        for name in ("settings.json", "settings.json.bak"):  # yedek kopya da yüklenmesin
            p = os.path.join(manager.APP_DIR, name)
            if os.path.exists(p):
                os.remove(p)

    def test_per_item_limit_survives_restart(self):
        m = self.mgr()
        it = m.add_http(self.s.url("/f5.bin"), os.path.join(newdir(), "l.bin"), start=False)
        m.set_item_limit(it.id, 256)
        m.save()
        m2 = self.mgr()
        self.assertEqual(m2.items[it.id].extra.get("speed_limit_kb"), 256)


# ---------------------------------------------------------------------------------------------- köprü (tarayıcı eklentisi)
class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = server.start(0)
        cls.port = cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, path, body=None, headers=None, method="POST"):
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                   data=None if body is None else json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, {}

    def drain(self):
        while not server.requests.empty():
            server.requests.get()

    def test_ping(self):
        self.assertEqual(self.req("/ping", method="GET"), (200, {"app": "TurboDM"}))

    def test_requires_custom_header(self):
        self.drain()
        self.assertEqual(self.req("/add", {"url": "https://x"})[0], 403)
        self.assertTrue(server.requests.empty())

    def test_rejects_dns_rebinding_host(self):
        self.drain()
        code, _ = self.req("/quit", {}, {"X-TurboDM": "1", "Host": "kotu-site.com"})
        self.assertEqual(code, 403)
        self.assertTrue(server.requests.empty(), "başka alan adından gelen istek kabul edildi")

    def test_preflight_denied(self):
        self.assertEqual(self.req("/add", None, method="OPTIONS")[0], 403)

    def test_bad_json(self):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/add", data=b"{bozuk",
                                   headers={"X-TurboDM": "1", "Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(r, timeout=5)
        self.assertEqual(cm.exception.code, 400)

    def test_add_accepted(self):
        self.drain()
        self.assertEqual(self.req("/add", {"url": "https://x/y.zip"}, {"X-TurboDM": "1"})[0], 200)
        self.assertEqual(server.requests.get(timeout=2)["url"], "https://x/y.zip")

    def test_handler_errors_are_reported(self):
        server.handlers["/formats"] = lambda d: (_ for _ in ()).throw(RuntimeError("deneme hatası"))
        try:
            self.assertEqual(self.req("/formats", {"url": "https://x"}, {"X-TurboDM": "1"}),
                             (200, {"error": "deneme hatası"}))
        finally:
            server.handlers.pop("/formats", None)


class SingleInstanceTests(unittest.TestCase):
    def test_foreign_program_on_port_is_not_mistaken_for_turbodm(self):
        class Foreign(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")
            do_POST = do_GET
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Foreign)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            import main
            with mock.patch.object(main, "_port", return_value=srv.server_address[1]):
                self.assertFalse(main._is_running())
                self.assertFalse(main._send_to_running(None), "yabancı program TurboDM sanıldı → TurboDM açılmazdı")
        finally:
            srv.shutdown()


# ---------------------------------------------------------------------------------------------- Windows kayıtları
@unittest.skipUnless(os.name == "nt", "yalnızca Windows")
class WinAssocTests(unittest.TestCase):
    ROOT_KEY = r"Software\TurboDM_UnitTest"   # gerçek kayıtlara dokunmamak için ayrı test anahtarı

    def tearDown(self):
        from turbodm import winassoc
        winassoc._delete_tree(self.ROOT_KEY)

    def test_uninstalling_one_copy_keeps_other_installs_registration(self):
        from turbodm import winassoc
        a = '"C:\\Program Files\\TurboDM\\TurboDM.exe" {}'
        b = '"C:\\Users\\x\\AppData\\Local\\TurboDM-Test\\TurboDM.exe" {}'
        with mock.patch.object(winassoc, "launch_command", lambda extra="": a.format(extra).strip()):
            winassoc.register(self.ROOT_KEY)
            self.assertTrue(winassoc.is_registered(self.ROOT_KEY))
        with mock.patch.object(winassoc, "launch_command", lambda extra="": b.format(extra).strip()):
            winassoc.unregister(self.ROOT_KEY)          # başka kopyanın kaldırılması
        classes = self.ROOT_KEY + r"\Classes"
        self.assertEqual(winassoc._get(classes + r"\.torrent"), "TurboDM.torrent", "öteki kurulumun kaydı silindi")
        self.assertIsNotNone(winassoc._get(classes + r"\TurboDM.torrent\shell\open\command"))
        self.assertIsNotNone(winassoc._get(self.ROOT_KEY + r"\RegisteredApplications", "TurboDM"))
        with mock.patch.object(winassoc, "launch_command", lambda extra="": a.format(extra).strip()):
            winassoc.unregister(self.ROOT_KEY)          # kendi kaydı: silinmeli
            self.assertFalse(winassoc.is_registered(self.ROOT_KEY))
        self.assertIsNone(winassoc._get(classes + r"\TurboDM.torrent\shell\open\command"))
        self.assertIsNone(winassoc._get(self.ROOT_KEY + r"\RegisteredApplications", "TurboDM"))


# ---------------------------------------------------------------------------------------------- kaldırma temizliği
class CleanupTests(unittest.TestCase):
    def test_cleanup_only_touches_turbodm_files(self):
        from turbodm import cleanup
        base = newdir()
        root = os.path.join(base, "Downloads", "TurboDM")
        desk = os.path.join(base, "Desktop")

        def mk(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(b"x")
        os.makedirs(manager.APP_DIR, exist_ok=True)
        json.dump({"download_root": root}, open(os.path.join(manager.APP_DIR, "settings.json"), "w"))
        mk(os.path.join(root, "Programs", "setup.exe.tdm"))
        mk(os.path.join(root, "Video", "bitti.mp4"))
        mk(os.path.join(root, "Video", "Film.f137.mp4.tdm"))
        mk(os.path.join(root, "Video", "Film.2023.mkv"))     # kullanıcının dosyası: aynı önek
        mk(os.path.join(desk, "rapor.pdf"))
        mk(os.path.join(desk, "kendi_dosyam.txt"))
        items = [{"kind": "http", "path": os.path.join(root, "Programs", "setup.exe"), "status": "stopped"},
                 {"kind": "http", "path": os.path.join(root, "Video", "bitti.mp4"), "status": "completed"},
                 {"kind": "ytdlp", "path": os.path.join(root, "Video", "Film.mp4"), "status": "stopped"},
                 {"kind": "http", "path": os.path.join(desk, "rapor.pdf"), "status": "completed"}]
        json.dump(items, open(os.path.join(manager.APP_DIR, "downloads.json"), "w"))
        cleanup.cleanup(registry=False, partials=True, downloads=True, appdata=False)
        self.assertFalse(os.path.exists(os.path.join(root, "Programs", "setup.exe.tdm")))
        self.assertFalse(os.path.exists(os.path.join(root, "Video", "Film.f137.mp4.tdm")))
        self.assertFalse(os.path.exists(os.path.join(root, "Video", "bitti.mp4")))
        self.assertTrue(os.path.exists(os.path.join(root, "Video", "Film.2023.mkv")), "ilgisiz dosya silindi")
        self.assertTrue(os.path.exists(os.path.join(desk, "kendi_dosyam.txt")), "ilgisiz dosya silindi")
        self.assertTrue(os.path.isdir(desk), "kullanıcının klasörü silindi")


if __name__ == "__main__":
    unittest.main(verbosity=2)
