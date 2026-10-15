"""Forum tanıtım görseli: docs/forum/turbodm-tanitim.png (yerelde kalır, depoya girmez).

  python installer/make_forum_banner.py

Ekran görüntüsü docs/github/ekran-koyu.png'den alınır (önce docs/github/ekran_goruntusu.py ile güncelleyin).
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter,  # noqa: E402
                           QPainterPath, QPen, QRadialGradient)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

W, H = 1600, 900
FEATURES = [
    ("⚡", "Çok bağlantılı hızlı indirme", "Kaldığı yerden devam, hız sınırı, kuyruk"),
    ("🎬", "Video yakalayıcı", "Sayfadaki videoyu tek tıkla indir · MP4 / MKV / MP3"),
    ("🧲", "Torrent", "Magnet ve .torrent, dosya seçerek"),
    ("🌐", "Tarayıcı entegrasyonu", "Edge / Chrome eklentisi"),
    ("🔒", "Güvenli ve açık kaynak", "İmzalı güncellemeler · GPL v3 · veri toplamaz"),
    ("🌍", "7 dil", "Türkçe, English, Deutsch, Français…"),
]


def font(size, weight=QFont.Normal, family="Segoe UI"):
    f = QFont(family)
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


def main(out):
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    img = QImage(W, H, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)

    # arka plan: TurboDM lacivert, sağ üstte mavi parıltı
    bg = QLinearGradient(0, 0, W, H)
    bg.setColorAt(0, QColor("#0b1428"))
    bg.setColorAt(1, QColor("#0e1a33"))
    p.fillRect(img.rect(), bg)
    glow = QRadialGradient(QPointF(W * 0.78, H * 0.30), 620)
    glow.setColorAt(0, QColor(30, 111, 217, 110))
    glow.setColorAt(1, QColor(30, 111, 217, 0))
    p.fillRect(img.rect(), glow)

    # sol: logo, ad, slogan
    logo = QImage(os.path.join(ROOT, "installer", "turbodm.png"))
    p.drawImage(QRectF(70, 70, 96, 96), logo)
    p.setPen(QColor("#ffffff"))
    p.setFont(font(68, QFont.Bold))
    p.drawText(QRectF(185, 62, 600, 90), Qt.AlignVCenter, "TurboDM")
    p.setFont(font(26, QFont.DemiBold))
    p.setPen(QColor("#7fb2ff"))
    p.drawText(QRectF(188, 140, 700, 40), Qt.AlignVCenter, "Ücretsiz, Türkçe bir IDM alternatifi")

    # özellikler
    y = 230
    for icon, title, sub in FEATURES:
        p.setFont(font(30, family="Segoe UI Emoji"))
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(72, y, 50, 50), Qt.AlignCenter, icon)
        p.setFont(font(24, QFont.DemiBold))
        p.drawText(QRectF(138, y - 4, 520, 34), Qt.AlignVCenter, title)
        p.setFont(font(18))
        p.setPen(QColor("#9fb0cc"))
        p.drawText(QRectF(138, y + 28, 520, 28), Qt.AlignVCenter, sub)
        y += 82

    # sağ: ekran görüntüsü, gölge ve yuvarlak köşe
    shot = QImage(os.path.join(ROOT, "docs", "github", "ekran-koyu.png"))
    sw = 860
    sh = int(shot.height() * sw / shot.width())
    r = QRectF(W - sw - 60, 205, sw, sh)
    for i in range(18, 0, -2):  # yumuşak gölge
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 10))
        p.drawRoundedRect(r.adjusted(-i, -i + 8, i, i + 8), 14 + i, 14 + i)
    clip = QPainterPath()
    clip.addRoundedRect(r, 12, 12)
    p.save()
    p.setClipPath(clip)
    p.drawImage(r, shot)
    p.restore()
    p.setPen(QPen(QColor(127, 178, 255, 90), 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(r, 12, 12)

    # alt bant: indirme adresi ve rozetler
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(30, 111, 217))
    btn = QRectF(70, H - 120, 470, 64)
    p.drawRoundedRect(btn, 32, 32)
    p.setPen(QColor("#ffffff"))
    p.setFont(font(24, QFont.Bold))
    p.drawText(btn, Qt.AlignCenter, "⬇  github.com/wexaR-TDM/TurboDM")
    p.setFont(font(19))
    p.setPen(QColor("#9fb0cc"))
    p.drawText(QRectF(570, H - 120, W - 640, 64), Qt.AlignVCenter,
               "Windows 10 / 11  ·  Ücretsiz  ·  Reklamsız  ·  Açık kaynak")
    p.end()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "forum", "turbodm-tanitim.png"))
