"""Edge Add-ons (ve Chrome Web Store) için mağaza görselleri ve eklenti paketi.

Çıktı: store\\cikti\\
  logo_300.png            mağaza logosu (300x300)
  tanitim_440x280.png     küçük tanıtım görseli
  ekran_1_video.png       sayfadaki "Bu videoyu indir" düğmesi ve kalite menüsü (1280x800)
  ekran_2_eklenti.png     eklenti penceresi (1280x800)
  ekran_3_uygulama.png    TurboDM ana penceresi (1280x800)
  TurboDM-Eklenti-<sürüm>.zip   mağazaya yüklenecek paket
Kullanım: python store\\make_store_assets.py   (Microsoft Edge kurulu olmalı: ekran görüntüleri için)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "store", "cikti")
DEMO = os.path.join(ROOT, "store", "demo")
EXT = os.path.join(ROOT, "browser_extension")
W, H = 1280, 800

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "installer"))


def edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        p = os.path.join(base or "", "Microsoft", "Edge", "Application", "msedge.exe")
        if os.path.isfile(p):
            return p
    raise SystemExit("Microsoft Edge bulunamadı")


def shot(html, png):
    """Edge'i görünmez (headless) ve geçici bir profille çalıştırıp sayfanın görüntüsünü alır."""
    prof = tempfile.mkdtemp(prefix="tdm_store_edge_", dir=os.path.join(ROOT, "build"))
    try:
        subprocess.run([edge(), "--headless=new", f"--user-data-dir={prof}", "--no-first-run",
                        "--allow-file-access-from-files", "--hide-scrollbars", f"--window-size={W},{H}",
                        "--virtual-time-budget=4000", f"--screenshot={png}", "file:///" + html.replace("\\", "/")],
                       check=True, timeout=120, capture_output=True)
    finally:
        time.sleep(1)
        shutil.rmtree(prof, ignore_errors=True)
    if not os.path.isfile(png):
        raise SystemExit(f"ekran görüntüsü alınamadı: {png}")


def popup_frame():
    """Gerçek popup.html'i sahte tarayıcı ortamıyla çalıştıran kopya (görüntü için)."""
    html = open(os.path.join(EXT, "popup.html"), encoding="utf-8").read()
    stub = """<script>
window.chrome = {
  storage: { local: { get(d, cb) { cb({ enabled: true, grabber: true }); }, set() {} } },
  tabs: { query(q, cb) { cb([{ id: 1, url: "https://ornekvideo.test/izle/123", title: "Doğa Belgeseli" }]); } },
  runtime: { sendMessage(m, cb) { cb([{ url: "https://cdn.ornekvideo.test/master.m3u8", label: "Video akışı (HLS) · 1080p" },
                                     { url: "https://cdn.ornekvideo.test/tanitim.mp4", label: "Video · 48,2 MB · video/mp4" }]); } },
};
window.fetch = () => Promise.resolve({ json: () => Promise.resolve({ app: "TurboDM" }) });
</script>
"""
    html = html.replace('<script src="popup.js">', stub + '<script src="../../browser_extension/popup.js">')
    path = os.path.join(DEMO, "popup_frame.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def qt_assets():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter
    from PySide6.QtWidgets import QApplication
    import make_icon

    app = QApplication.instance() or QApplication([])
    make_icon.render(300).save(os.path.join(OUT, "logo_300.png"))

    # küçük tanıtım görseli
    img = make_icon.wizard_background(440 / 620).scaled(440, 280, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.drawImage(34, 80, make_icon.render(120))
    f = QFont("Segoe UI")
    f.setPixelSize(40)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(176, 96, 250, 50, Qt.AlignLeft | Qt.AlignVCenter, "TurboDM")
    f.setPixelSize(16)
    f.setBold(False)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255, 210))
    p.drawText(178, 146, 250, 60, Qt.AlignLeft | Qt.TextWordWrap, "İndirmeleri ve videoları\nTurboDM'e gönderin")
    p.end()
    img.save(os.path.join(OUT, "tanitim_440x280.png"))

    # büyük tanıtım görseli (1400x560)
    big = make_icon.wizard_background(1400 / 620).scaled(1400, 560, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    p = QPainter(big)
    p.setRenderHint(QPainter.Antialiasing)
    p.drawImage(150, 130, make_icon.render(300))
    f = QFont("Segoe UI")
    f.setPixelSize(110)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(520, 120, 840, 150, Qt.AlignLeft | Qt.AlignVCenter, "TurboDM")
    f.setPixelSize(38)
    f.setBold(False)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255, 220))
    p.drawText(526, 280, 840, 60, Qt.AlignLeft | Qt.AlignVCenter, "İndirmeleri ve videoları tek tıkla TurboDM'e")
    f.setPixelSize(26)
    p.setFont(f)
    p.setPen(QColor(150, 190, 245))
    p.drawText(528, 350, 840, 50, Qt.AlignLeft | Qt.AlignVCenter,
               "Çok bağlantılı indirme  ·  Video yakalayıcı  ·  Kaldığı yerden devam")
    p.end()
    big.save(os.path.join(OUT, "tanitim_buyuk_1400x560.png"))

    # TurboDM ana penceresi, örnek indirmelerle (gerçek kullanıcı verisine dokunmaz)
    tmp = tempfile.mkdtemp(prefix="tdm_store_app_", dir=os.path.join(ROOT, "build"))
    os.environ["APPDATA"] = os.path.join(tmp, "appdata")
    from turbodm import manager as M
    M.APP_DIR = os.path.join(os.environ["APPDATA"], "TurboDM")
    M.TORRENT_DIR = os.path.join(M.APP_DIR, "torrents")
    M.DEFAULT_SETTINGS.update(download_root=os.path.join(tmp, "dl"), server_port=9699, torrent_port=6999,
                              auto_update_check=False)
    from turbodm.gui import MainWindow, apply_theme
    app.setStyle("Fusion")
    apply_theme(app)
    app.setFont(QFont("Segoe UI", 9))  # ekran dışı çizimde Windows'un yazı tipi kendiliğinden seçilmez
    mgr = M.Manager()
    rows = [("Doğa Belgeseli - Kuzey Ormanları.mp4", "downloading", 512, 0.62, 48.4, "video"),
            ("ubuntu-24.04-desktop-amd64.iso", "downloading", 5900, 0.31, 61.2, "general"),
            ("Proje Sunumu.pdf", "completed", 14, 1, 0, "document"),
            ("Albüm - Canlı Kayıt.zip", "completed", 820, 1, 0, "compressed"),
            ("kurulum-araci.exe", "queued", 96, 0, 0, "program")]
    for name, status, mb, frac, speed, cat in rows:
        it = mgr.add_http(f"https://ornek.test/{name}", os.path.join(tmp, "dl", name), start=False)
        it.size, it.status, it.category = mb * 1024 * 1024, status, cat
        it.done_bytes = int(it.size * frac)
        it.speed = speed * 1024 * 1024
        it.in_queue = status == "queued"
    win = MainWindow(mgr)
    win.resize(W, H)
    win.show()
    for _ in range(20):
        app.processEvents()
        time.sleep(0.02)
    win.refresh(force=True)
    app.processEvents()
    win.grab().toImage().scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).save(
        os.path.join(OUT, "ekran_3_uygulama.png"))
    win.quit_app() if hasattr(win, "quit_app") else None
    shutil.rmtree(tmp, ignore_errors=True)


def package():
    ver = json.load(open(os.path.join(EXT, "manifest.json"), encoding="utf-8"))["version"]
    zpath = os.path.join(OUT, f"TurboDM-Eklenti-{ver}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(EXT):
            for n in files:
                full = os.path.join(folder, n)
                z.write(full, os.path.relpath(full, EXT).replace("\\", "/"))  # manifest.json kökte
    return zpath


if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    shot(os.path.join(DEMO, "video.html"), os.path.join(OUT, "ekran_1_video.png"))
    popup_frame()
    shot(os.path.join(DEMO, "popup.html"), os.path.join(OUT, "ekran_2_eklenti.png"))
    qt_assets()
    print(package())
    for n in sorted(os.listdir(OUT)):
        print(" ", n)
    sys.stdout.flush()
    os._exit(0)  # Qt'nin kapanışta verdiği anlamsız hata kodunu atla (tüm dosyalar yazıldı)
