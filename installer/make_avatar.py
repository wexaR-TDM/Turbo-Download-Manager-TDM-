"""TurboDM temalı GitHub profil resmi (1024x1024 PNG). GitHub resmi daire şeklinde kırpar: önemli her şey
ortadaki dairenin içinde kalır. Çıktı: docs/avatar.png"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen,  # noqa: E402
                           QRadialGradient, QImage)

S = 1024


def main(out):
    app = QGuiApplication([])  # noqa: F841
    img = QImage(S, S, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    # koyu lacivert zemin (kurulum sihirbazı ve tema ile aynı aile)
    g = QLinearGradient(0, 0, S * 0.6, S)
    g.setColorAt(0, QColor("#0b1324"))
    g.setColorAt(1, QColor("#0f2a57"))
    p.fillRect(img.rect(), g)
    glow = QRadialGradient(S * 0.5, S * 0.42, S * 0.55)
    glow.setColorAt(0, QColor(59, 140, 240, 110))
    glow.setColorAt(1, QColor(59, 140, 240, 0))
    p.fillRect(img.rect(), glow)
    # hız çizgileri (sol)
    for i, (y, w, a) in enumerate(((0.40, 0.17, 150), (0.50, 0.23, 200), (0.60, 0.15, 120))):
        pen = QPen(QColor(120, 180, 255, a), S * 0.022)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(S * (0.16), S * y), QPointF(S * (0.16 + w), S * y))
    # ana daire: TurboDM mavisi degrade
    c, r = QPointF(S * 0.56, S * 0.5), S * 0.27
    cg = QLinearGradient(0, c.y() - r, 0, c.y() + r)
    cg.setColorAt(0, QColor("#4a9bff"))
    cg.setColorAt(1, QColor("#1557b8"))
    p.setPen(QPen(QColor(255, 255, 255, 40), S * 0.008))
    p.setBrush(cg)
    p.drawEllipse(c, r, r)
    # beyaz indirme oku + taban çizgisi
    u = r / 32.0
    ox, oy = c.x() - 32 * u, c.y() - 32 * u
    path = QPainterPath()
    for i, (x, y) in enumerate([(25, 13), (39, 13), (39, 32), (49, 32), (32, 49), (15, 32), (25, 32)]):
        (path.moveTo if i == 0 else path.lineTo)(ox + x * u, oy + y * u)
    path.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    p.drawPath(path)
    p.drawRoundedRect(QRectF(ox + 16 * u, oy + 52 * u, 32 * u, 4.5 * u), 2 * u, 2 * u)
    p.end()
    img.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "docs", "avatar.png"))
