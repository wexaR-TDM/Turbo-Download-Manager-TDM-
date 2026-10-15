"""TurboDM simgesini (mavi daire + beyaz ok) çok boyutlu .ico ve .png olarak üretir."""
import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter,  # noqa: E402
                           QPainterPath, QPen, QRadialGradient)


def render(size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 64.0
    g = QLinearGradient(0, 0, 0, size)
    g.setColorAt(0, QColor("#3b8cf0"))
    g.setColorAt(1, QColor("#1557b8"))
    p.setBrush(g)
    p.setPen(Qt.NoPen)
    p.drawEllipse(int(2 * s), int(2 * s), int(60 * s), int(60 * s))
    p.setBrush(QColor("white"))
    path = QPainterPath()
    for i, (x, y) in enumerate([(25, 12), (39, 12), (39, 32), (49, 32), (32, 50), (15, 32), (25, 32)]):
        (path.moveTo if i == 0 else path.lineTo)(x * s, y * s)
    path.closeSubpath()
    p.drawPath(path)
    p.fillRect(int(15 * s), int(52 * s), int(34 * s), max(1, int(4 * s)), QColor("white"))
    p.end()
    return img


# Marka renkleri (kurulum sihirbazı ve kaldırıcıyla ortak)
BG_TOP, BG_BOTTOM, ACCENT = "#0b1324", "#0f2347", "#3b8cf0"


def wizard_background(scale):
    """Sihirbaz sayfalarının arka planı: koyu lacivert degrade, hafif ızgara, ışıltı ve soluk logo."""
    w, h = int(620 * scale), int(460 * scale)
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, w * 0.4, h)
    g.setColorAt(0, QColor(BG_TOP))
    g.setColorAt(1, QColor(BG_BOTTOM))
    p.fillRect(img.rect(), g)
    # sağ üstte mavi ışıltı
    rg = QRadialGradient(w * 0.92, h * 0.05, w * 0.55)
    glow = QColor(ACCENT)
    glow.setAlpha(70)
    rg.setColorAt(0, glow)
    glow.setAlpha(0)
    rg.setColorAt(1, glow)
    p.fillRect(img.rect(), rg)
    # ince ızgara (hız/ağ çağrışımı)
    pen = QPen(QColor(255, 255, 255, 10))
    pen.setWidthF(1 * scale)
    p.setPen(pen)
    step = int(28 * scale)
    for x in range(0, w, step):
        p.drawLine(x, 0, x, h)
    for y in range(0, h, step):
        p.drawLine(0, y, w, y)
    # sağ altta çok soluk büyük logo (yazıların okunurluğunu bozmaz)
    p.setOpacity(0.07)
    big = int(300 * scale)
    p.drawImage(w - int(big * 0.78), h - int(big * 0.78), render(big))
    p.end()
    return img


# Kurulum sihirbazı yan görselindeki alt başlık, kurulumda seçilen dile göre (TurboDM.iss → LoadSideImage)
SIDE_SUBTITLE = {
    "en": "Download Manager", "tr": "İnternet İndirme Yöneticisi", "de": "Download-Manager",
    "fr": "Gestionnaire de téléchargement", "es": "Gestor de descargas", "ar": "مدير التنزيل",
    "it": "Gestore di download",
}


def wizard_side(scale, lang="en"):
    """Karşılama ve bitiş sayfalarındaki sol panel."""
    w, h = int(164 * scale), int(314 * scale)
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor("#1a5fd0"))
    g.setColorAt(1, QColor("#0a2a63"))
    p.fillRect(img.rect(), g)
    # hız çizgileri
    for i, (y, a) in enumerate(((0.74, 40), (0.78, 28), (0.82, 18))):
        pen = QPen(QColor(255, 255, 255, a))
        pen.setWidthF(2 * scale)
        p.setPen(pen)
        p.drawLine(int(w * 0.12), int(h * y), int(w * (0.88 - i * 0.12)), int(h * y))
    logo = int(96 * scale)
    p.drawImage((w - logo) // 2, int(54 * scale), render(logo))
    p.setPen(QColor("white"))
    f = QFont("Segoe UI")
    f.setPixelSize(int(22 * scale))
    f.setBold(True)
    p.setFont(f)
    p.drawText(0, int(160 * scale), w, int(32 * scale), Qt.AlignCenter, "TurboDM")
    f.setPixelSize(int(11 * scale))
    f.setBold(False)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255, 200))
    p.drawText(0, int(190 * scale), w, int(20 * scale), Qt.AlignCenter, SIDE_SUBTITLE[lang])
    f.setPixelSize(int(9 * scale))
    p.setFont(f)
    p.setPen(QColor(255, 255, 255, 150))
    p.drawText(0, h - int(30 * scale), w, int(20 * scale), Qt.AlignCenter, "HTTP · FTP · Video · Torrent")
    p.end()
    return img


def png_bytes(img):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def write_ico(path, sizes=(16, 20, 24, 32, 40, 48, 64, 128, 256)):
    pngs = [png_bytes(render(s)) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, data = b"", b""
    for s, png in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    with open(path, "wb") as f:
        f.write(header + entries + data)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    app = QGuiApplication([])
    write_ico(os.path.join(out, "turbodm.ico"))
    render(256).save(os.path.join(out, "turbodm.png"))
    # Kurulum sihirbazının yan görseli (164x314) ve küçük görseli (55x55)
    # Kurulum sihirbazı görselleri: %100, %150, %200 ölçek (Inno en uygununu seçer)
    for scale, tag in ((1.0, "100"), (1.5, "150"), (2.0, "200")):
        wizard_background(scale).save(os.path.join(out, f"wizard_bg_{tag}.png"))
        wizard_side(scale).save(os.path.join(out, f"wizard_side_{tag}.png"))  # varsayılan: İngilizce
        os.makedirs(os.path.join(out, "wizard"), exist_ok=True)
        for lang in SIDE_SUBTITLE:  # her kurulum dili için ayrı yan görsel
            wizard_side(scale, lang).save(os.path.join(out, "wizard", f"side_{lang}_{tag}.png"))
        render(int(58 * scale)).save(os.path.join(out, f"wizard_small_{tag}.png"))
    # Tarayıcı eklentisinin simgeleri (araç çubuğu, eklentiler sayfası, mağaza)
    ext = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "browser_extension", "icons")
    os.makedirs(ext, exist_ok=True)
    for s in (16, 32, 48, 128):
        render(s).save(os.path.join(ext, f"icon{s}.png"))
    print("ok")
