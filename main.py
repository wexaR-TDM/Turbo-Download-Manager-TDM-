"""TurboDM giriş noktası.

Kullanım:
    TurboDM.exe                          → programı aç (zaten açıksa öne getir)
    TurboDM.exe <url|magnet|.torrent>    → çalışan programa gönder (yoksa açıp ekle)
    TurboDM.exe --tray                   → pencereyi göstermeden sistem tepsisinde başla
    TurboDM.exe --minimized --resume     → güncelleme sonrası: görev çubuğunda simge durumunda aç,
                                           kapanırken inmekte olanları sürdür

Kurulum/kaldırma araçları (kurulum programı kullanır):
    --quit                               → çalışan TurboDM'i düzgünce kapat
    --register-assoc / --unregister-assoc → magnet: ve .torrent ilişkilendirmesi
    --autostart on|off                   → Windows açılışında başlatma
    --set-language tr|en|de|fr|es|ar|it  → kurulumda seçilen dili ayarlara yaz
    --cleanup [--partials] [--downloads] [--appdata]  → kaldırma temizliği (kayıt defteri hep temizlenir)
    --selftest <rapor.json>              → bileşen denetimi (başka bilgisayarda sorun tespiti için)
"""
import json
import os
import sys
import time
import urllib.request

from turbodm.appinfo import APP_USER_MODEL_ID, MUTEX_NAME
from turbodm.manager import APP_DIR, DEFAULT_SETTINGS
from turbodm.i18n import _t


def _port():
    try:
        with open(os.path.join(APP_DIR, "settings.json"), encoding="utf-8") as f:
            return json.load(f).get("server_port", DEFAULT_SETTINGS["server_port"])
    except (OSError, ValueError):
        return DEFAULT_SETTINGS["server_port"]


def _is_running():
    """Portta gerçekten TurboDM mi var? (Başka bir program aynı portu kullanıyorsa onu TurboDM sanma.)"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{_port()}/ping", timeout=2) as r:
            return r.status == 200 and json.loads(r.read(4096) or b"{}").get("app") == "TurboDM"
    except (OSError, ValueError):
        return False


def _post(path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{_port()}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-TurboDM": "1"})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except OSError:
        return False


def _send_to_running(arg):
    """Program zaten açıksa isteği ona ilet (tek örnek çalışma)."""
    if not _is_running():
        return False
    if arg:
        return _post("/add", {"url": os.path.abspath(arg) if os.path.isfile(arg) else arg})
    return _post("/show", {})


def _quit_running(timeout=20):
    if not _post("/quit", {}):
        return True
    end = time.time() + timeout
    while time.time() < end:
        if not _is_running():
            time.sleep(0.5)  # süreç kapanışını bitirsin
            return True
        time.sleep(0.3)
    return False


def _selftest(out_path):
    """Kurulu sürümün tüm bileşenlerini dener ve JSON rapor yazar."""
    rep = {}

    def check(name, fn):
        try:
            rep[name] = {"ok": True, "info": fn()}
        except Exception as e:  # noqa: BLE001
            rep[name] = {"ok": False, "info": f"{type(e).__name__}: {e}"}

    def qt():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QWidget
        import PySide6
        app = QApplication.instance() or QApplication([])
        w = QWidget()
        w.resize(10, 10)
        w.grab()
        return "PySide6 " + PySide6.__version__ + " / " + app.platformName()

    def torrent():
        from turbodm import torrent as t
        e = t.TorrentEngine(port=6977)
        v = t.lt.__version__
        e.shutdown()
        return "libtorrent " + v

    def aes():
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        k = b"k" * 16
        enc = Cipher(algorithms.AES(k), modes.CBC(b"\0" * 16)).encryptor()
        ct = enc.update(b"x" * 16) + enc.finalize()
        dec = Cipher(algorithms.AES(k), modes.CBC(b"\0" * 16)).decryptor()
        assert dec.update(ct) + dec.finalize() == b"x" * 16
        return "AES-128 ok"

    def ffmpeg():
        import subprocess
        from turbodm.hls import find_ffmpeg
        p = find_ffmpeg()
        if not p:
            raise RuntimeError(_t("ffmpeg bulunamadı"))
        r = subprocess.run([p, "-hide_banner", "-version"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p + " | " + r.stdout.decode(errors="replace").splitlines()[0]

    def https():
        import ssl
        ctx = ssl.create_default_context()
        return _t("{0} kök sertifika (Windows deposu) yüklü, {1}").format(len(ctx.get_ca_certs()), ssl.OPENSSL_VERSION)

    def engine():
        import tempfile
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from turbodm.engine import HttpTask, SpeedLimiter
        data = os.urandom(3 * 1024 * 1024)

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                import re
                a, b = re.match(r"bytes=(\d+)-(\d*)", self.headers.get("Range", "bytes=0-")).groups()
                a, b = int(a), (int(b) if b else len(data) - 1)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
                self.send_header("Content-Length", str(b - a + 1))
                self.end_headers()
                self.wfile.write(data[a:b + 1])

        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        class It:
            pass
        it = It()
        it.url, it.headers, it.size, it.resumable = f"http://127.0.0.1:{srv.server_port}/f", {}, None, True
        it.segments, it.connections = [], 8
        it.path = os.path.join(tempfile.mkdtemp(), "f.bin")
        t = HttpTask(it, SpeedLimiter(0))
        t.start()
        end = time.time() + 30
        while t.state not in ("completed", "error") and time.time() < end:
            time.sleep(0.05)
        srv.shutdown()
        with open(it.path, "rb") as f:
            ok = f.read() == data
        import shutil
        shutil.rmtree(os.path.dirname(it.path), ignore_errors=True)
        if not ok:
            raise RuntimeError(f"dosya bozuk ({t.state} {t.error})")
        return _t("8 bağlantılı 3 MB indirme birebir doğru")

    def youtube():
        import subprocess
        from turbodm import ytdlp
        if not ytdlp.ytdlp_path():
            raise RuntimeError(_t("yt-dlp bulunamadı"))
        d = ytdlp.deno_path()
        if not d:
            raise RuntimeError(_t("deno (JavaScript motoru) bulunamadı"))
        r = subprocess.run([d, "--version"], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return f"yt-dlp {ytdlp.version()} ({ytdlp.ytdlp_path()}) | {r.stdout.splitlines()[0]}"

    for name, fn in (("qt_arayuz", qt), ("torrent", torrent), ("aes", aes), ("ffmpeg", ffmpeg),
                     ("https", https), ("indirme_motoru", engine), ("youtube", youtube)):
        check(name, fn)
    rep["hepsi_tamam"] = all(v["ok"] for v in rep.values() if isinstance(v, dict))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    return 0 if rep["hepsi_tamam"] else 1


def _tool_mode(args):
    """Kurulum programının çağırdığı komutlar. None → normal GUI başlangıcı."""
    from turbodm import winassoc
    if "--selftest" in args:
        i = args.index("--selftest")
        return _selftest(args[i + 1] if i + 1 < len(args) else "selftest.json")
    if "--quit" in args:
        return 0 if _quit_running() else 1
    if "--register-assoc" in args:
        winassoc.register()
        return 0
    if "--unregister-assoc" in args:
        winassoc.unregister()
        return 0
    if "--set-language" in args:  # kurulumda seçilen dil
        from turbodm import i18n
        i = args.index("--set-language")
        return 0 if i + 1 < len(args) and i18n.save_language_setting(args[i + 1]) else 1
    if "--autostart" in args:
        i = args.index("--autostart")
        winassoc.set_autostart(i + 1 < len(args) and args[i + 1] == "on")
        return 0
    if "--cleanup" in args:
        _quit_running()
        from turbodm.cleanup import cleanup
        cleanup(registry=True, partials="--partials" in args,
                downloads="--downloads" in args, appdata="--appdata" in args)
        return 0
    return None


def main():
    args = sys.argv[1:]
    rc = _tool_mode(args)
    if rc is not None:
        sys.exit(rc)

    tray = "--tray" in args  # Windows açılışında: pencereyi göstermeden tepside başla
    args = [a for a in args if not a.startswith("--")]
    arg = args[0] if args else None
    if tray and not arg:
        if _is_running():
            return
    elif _send_to_running(arg):
        return

    if sys.platform == "win32" and "--restart" in sys.argv[1:]:
        # dil değişikliği sonrası yeniden başlatma: eski kopya tamamen kapanana kadar bekle
        import ctypes
        for _ in range(60):
            h = ctypes.windll.kernel32.OpenMutexW(0x00100000, False, MUTEX_NAME)  # SYNCHRONIZE
            if not h:
                break
            ctypes.windll.kernel32.CloseHandle(h)
            time.sleep(0.25)
    if sys.platform == "win32":
        import ctypes
        # Görev çubuğunda Python simgesi yerine TurboDM simgesi görünsün
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        # Tek örnek: kurulum/kaldırma programı da bu mutex ile programın açık olduğunu anlar.
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)  # noqa: F841
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            # Başka bir TurboDM o an açılıyor (çift tıklama vb.): köprüsü hazır olunca isteği ona ilet, ikinci
            # kopya açılmasın (iki kopya aynı listeyi yönetip birbirinin kaydını ezerdi).
            for _ in range(40):
                if _is_running():
                    _send_to_running(arg)
                    return
                time.sleep(0.25)
            return

    from PySide6.QtWidgets import QApplication
    from turbodm.gui import MainWindow
    from turbodm.manager import Manager

    app = QApplication(sys.argv)
    app.setApplicationName("TurboDM")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    from turbodm import i18n
    i18n.apply_to_app(app)  # Qt'nin kendi düğme metinleri ve Arapça için sağdan sola düzen
    from turbodm.gui import apply_theme
    apply_theme(app)
    mgr = Manager()
    if "--resume" in sys.argv[1:]:  # otomatik güncelleme sonrası: inmekte olanlar kaldığı yerden sürsün
        mgr.resume_interrupted()
    win = MainWindow(mgr)
    if "--minimized" in sys.argv[1:] and not arg:  # güncelleme sonrası: görev çubuğunda, öne çıkmadan
        win.showMinimized()
    elif not tray or arg:
        win.show()
    if arg:
        win.add_source(os.path.abspath(arg) if os.path.isfile(arg) else arg)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
