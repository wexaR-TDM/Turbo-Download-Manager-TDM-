"""PySide6 arayüzü: IDM tarzı ana pencere, indirme durumu penceresi, ayarlar, zamanlayıcı."""
import os
import re
import subprocess
import threading
import time
import urllib.parse
from datetime import datetime

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QSpinBox, QSplitter, QStyle,
    QSystemTrayIcon, QTableWidget, QTableWidgetItem, QTabWidget, QTimeEdit, QToolBar,
    QGroupBox, QProgressBar, QTextBrowser, QStyledItemDelegate, QStyleOptionViewItem,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import convert
from . import hls
from . import server
from . import theme
from . import updater
from . import ytdlp
from .appinfo import VERSION
from . import torrent as tmod
from . import winassoc
from .engine import fetch_torrent, filename_from_url, looks_like_torrent, probe, sanitize_filename
from .manager import CATCH_EXTS, CATEGORIES, TORRENT_DIR, Manager, category_for

APP_NAME = "TurboDM"

STATUS_TEXT = {
    "stopped": "Durduruldu", "queued": "Kuyrukta", "connecting": "Bağlanıyor…",
    "downloading": "İndiriliyor", "completed": "Tamamlandı", "error": "Hata",
    "seeding": "Paylaşılıyor", "converting": "Dönüştürülüyor…",
}


# ------------------------------------------------------------------ biçimlendirme
def fmt_size(n):
    if n is None:
        return "Bilinmiyor"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


def fmt_speed(b):
    return fmt_size(b) + "/s" if b and b > 0 else ""


def fmt_time(s):
    if s is None:
        return ""
    s = int(s)
    if s >= 86400:
        return f"{s // 86400}g {s % 86400 // 3600}sa"
    if s >= 3600:
        return f"{s // 3600}sa {s % 3600 // 60}dk"
    if s >= 60:
        return f"{s // 60}dk {s % 60}sn"
    return f"{s}sn"


def make_icon(color="#1e6fd9"):
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, 60, 60)
    p.setBrush(QColor("white"))
    path = QPainterPath()
    path.moveTo(25, 12); path.lineTo(39, 12); path.lineTo(39, 32); path.lineTo(49, 32)
    path.lineTo(32, 50); path.lineTo(15, 32); path.lineTo(25, 32); path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def load_icon():
    """Kurulu sürümde exe'nin yanındaki, geliştirmede installer/ klasöründeki simge."""
    from .appinfo import install_dir
    for p in (os.path.join(install_dir(), "turbodm.ico"),
              os.path.join(install_dir(), "installer", "turbodm.ico")):
        if os.path.isfile(p):
            return QIcon(p)
    return make_icon()


def apply_theme(app, mode="auto"):
    """TurboDM teması (theme.py): Windows'un açık/koyu moduna kendiliğinden uyar; vurgu her zaman TurboDM
    mavisi (aksi hâlde Qt, Windows'un vurgu rengini, ör. kırmızıyı alırdı)."""
    theme.install(app, mode)


def bring_to_front(w):
    """Pencereyi ekranın önüne getir. Windows, arka plandaki bir programın (TurboDM tarayıcıdan tetiklenince
    arka plandadır) pencereyi öne almasını engeller ("odak çalma" koruması); yalnızca görev çubuğunda
    yanıp söner. Ön plandaki iş parçacığına geçici olarak bağlanmak ve pencereyi kısa süre 'her zaman üstte'
    yapmak bu korumayı yasal yoldan aşar."""
    w.show()
    w.setWindowState((w.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
    w.raise_()
    w.activateWindow()
    if os.name != "nt":
        return
    try:
        import ctypes
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = int(w.winId())
        fg = u32.GetForegroundWindow()
        fg_tid = u32.GetWindowThreadProcessId(fg, None)
        me = k32.GetCurrentThreadId()
        attached = fg_tid and fg_tid != me and u32.AttachThreadInput(me, fg_tid, True)
        try:
            HWND_TOPMOST, HWND_NOTOPMOST, FLAGS = -1, -2, 0x0001 | 0x0002 | 0x0040  # NOSIZE|NOMOVE|SHOWWINDOW
            u32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, FLAGS)
            u32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, FLAGS)
            u32.BringWindowToTop(hwnd)
            u32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                u32.AttachThreadInput(me, fg_tid, False)
    except Exception:  # noqa: BLE001
        pass


def standalone_window(w):
    """Pencereyi bağımsız uygulama penceresi gibi yap: başlıkta küçült / ekranı kapla / kapat düğmeleri,
    görev çubuğunda kendi düğmesi (küçültülünce oraya iner, oradan geri açılır)."""
    w.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
                     | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
    if os.name != "nt":
        return
    try:
        import ctypes
        u32 = ctypes.windll.user32
        hwnd = int(w.winId())  # yerel pencere gösterilmeden önce oluşturulur
        GWL_EXSTYLE, WS_EX_APPWINDOW = -20, 0x00040000
        u32.SetWindowLongW(hwnd, GWL_EXSTYLE, u32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_APPWINDOW)
    except Exception:  # noqa: BLE001
        pass


def open_path(path):
    if os.path.exists(path):
        os.startfile(path)  # noqa: S606 (Windows)


def open_folder(path):
    if os.path.isfile(path):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if os.path.isdir(folder):
            os.startfile(folder)


def is_dash(url, content_type=""):
    """DASH (MPEG-DASH, .mpd) video akışı mı?"""
    return ((content_type or "").split(";")[0].strip().lower() == "application/dash+xml"
            or urllib.parse.urlparse(url).path.lower().endswith(".mpd"))


def is_magnet(text):
    return text.strip().lower().startswith("magnet:?")


# ------------------------------------------------------------------ segment çubuğu
class SegmentBar(QWidget):
    """IDM'nin ünlü parçalı ilerleme çubuğu: her bağlantının indirdiği bölge ayrı görünür."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(24)
        self.size = 0
        self.segs = []

    def set_data(self, size, segs):
        self.size, self.segs = size or 0, segs
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath()
        clip.addRoundedRect(r, 6, 6)
        p.setClipPath(clip)
        p.fillRect(r, QColor(theme.T["track"]))   # koyu/açık temaya uyumlu zemin
        if self.size:
            w = r.width()
            for a, b, pos in self.segs:
                x0 = r.x() + a / self.size * w
                x1 = r.x() + min(pos, b + 1) / self.size * w
                if x1 > x0:
                    p.fillRect(QRectF(x0, r.y(), max(1.0, x1 - x0), r.height()), QColor(theme.T["accent"]))
            p.setPen(QPen(QColor(theme.T["surface"]), 1.5))   # bağlantılar arası ince ayraç
            for a, b, pos in self.segs:
                if a > 0:
                    x = r.x() + a / self.size * w
                    p.drawLine(QPointF(x, r.y()), QPointF(x, r.bottom()))
        p.setClipping(False)
        p.setPen(QColor(theme.T["border"]))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 6, 6)


class Bridge(QObject):
    probed = Signal(object, object)
    hls = Signal(object, object)
    video = Signal(object, object)
    done = Signal(object, object)       # genel arka plan işi sonucu
    progress = Signal(int, int)


class TorrentFilesTree(QTreeWidget):
    """Torrent içindeki dosyalar: klasör ağacı + onay kutuları (indirilecekleri seç)."""
    changed = Signal()

    def __init__(self, with_progress=False, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Dosya", "Boyut"] + (["İlerleme"] if with_progress else []))
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.header().setStretchLastSection(False)
        self.leaves = []
        self._building = False
        self.itemChanged.connect(lambda *_: None if self._building else self.changed.emit())

    def populate(self, files, priorities=None):
        """files: [(yol, boyut, dolgu_mu), ...]  priorities: [0..7] (0 = indirme)"""
        self._building = True
        self.clear()
        self.leaves, self.pads, folders = [], [], {}
        for i, (path, size, pad) in enumerate(files):
            self.pads.append(pad)
            if pad:
                continue
            parts = path.replace("\\", "/").split("/")
            parent = self.invisibleRootItem()
            for d in range(len(parts) - 1):
                key = "/".join(parts[:d + 1])
                if key not in folders:
                    f = QTreeWidgetItem([parts[d], ""])
                    f.setFlags(f.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                    f.setCheckState(0, Qt.Checked)
                    f.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                    parent.addChild(f)
                    folders[key] = f
                parent = folders[key]
            leaf = QTreeWidgetItem([parts[-1], fmt_size(size)])
            leaf.setFlags(leaf.flags() | Qt.ItemIsUserCheckable)
            on = priorities is None or i >= len(priorities) or priorities[i] > 0
            leaf.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
            parent.addChild(leaf)
            self.leaves.append((leaf, size))
        self.expandAll()
        self._building = False

    def priorities(self):
        """Tüm dosya indeksleri için öncelik listesi (dolgu dosyaları dahil)."""
        it = iter(self.leaves)
        return [4 if pad or next(it)[0].checkState(0) == Qt.Checked else 0 for pad in self.pads]

    def any_selected(self):
        return any(leaf.checkState(0) == Qt.Checked for leaf, _ in self.leaves)

    def selected_size(self):
        return sum(s for leaf, s in self.leaves if leaf.checkState(0) == Qt.Checked)

    def set_all(self, on):
        self._building = True
        for leaf, _ in self.leaves:
            leaf.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self._building = False
        self.changed.emit()

    def set_progress(self, done_list):
        done_list = [d for d, pad in zip(done_list, self.pads) if not pad]
        for (leaf, size), done in zip(self.leaves, done_list):
            txt = f"%{(done / size * 100) if size else 100:.1f}"
            if leaf.text(2) != txt:
                leaf.setText(2, txt)


# ------------------------------------------------------------------ dosya bilgisi
class FileInfoDialog(QDialog):
    """IDM'deki 'İndirme Dosyası Bilgisi' penceresi."""

    def __init__(self, win, url, headers=None, suggested=None, cookies=None, video_info=None, preselect=None):
        """video_info/preselect: tarayıcıdaki kalite menüsünden gelindiyse hazır bilgi ve seçilen biçim
        (yeniden sorgulanmaz; kalite ve uzantı seçili gelir, kullanıcı yalnızca yeri onaylar)."""
        super().__init__(win)
        self.win, self.mgr = win, win.mgr
        self.url, self.headers = url, headers or {}
        self.cookies = cookies or []     # tarayıcı eklentisinden (YouTube oturumu vb.)
        self.video_info = None           # yt-dlp ile bulunan site videosu
        self.info = {"size": None, "resumable": True}
        self.user_edited = False
        self.setWindowTitle("İndirme Dosyası Bilgisi")
        self.setMinimumWidth(560)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.url_edit = QLineEdit(url)
        self.cat = QComboBox()
        for key, (disp, _, _) in CATEGORIES.items():
            if key != "torrent":
                self.cat.addItem(disp, key)
        self.path_edit = QLineEdit()
        browse = QPushButton("…")
        browse.setObjectName("browse")
        browse.setFixedWidth(32)
        browse.clicked.connect(self._browse)
        prow = QHBoxLayout()
        prow.addWidget(self.path_edit)
        prow.addWidget(browse)
        self.desc = QLineEdit()
        self.size_lbl = QLabel("Sorgulanıyor…")
        self.size_lbl.setWordWrap(True)
        self.quality = QComboBox()   # yalnızca HLS videolarda görünür
        self.hls_info = None
        self.fmt = QComboBox()       # indirme bitince dönüştürme (video/ses)
        for key, (text, _) in convert.FORMATS.items():
            self.fmt.addItem(text, key)

        form = QFormLayout()
        self.form = form
        form.addRow("Adres (URL):", self.url_edit)
        form.addRow("Kalite:", self.quality)
        form.addRow("Biçim:", self.fmt)
        form.addRow("Kategori:", self.cat)
        form.addRow("Kayıt klasörü:", prow)
        form.addRow("Açıklama:", self.desc)
        form.addRow("Boyut:", self.size_lbl)
        form.setRowVisible(self.quality, False)
        form.setRowVisible(self.fmt, False)

        b_start = QPushButton("İndirmeyi Başlat")
        b_start.setDefault(True)
        b_later = QPushButton("Sonra İndir (kuyruğa ekle)")
        b_cancel = QPushButton("İptal")
        b_start.clicked.connect(lambda: self._go(True))
        b_later.clicked.connect(lambda: self._go(False))
        b_cancel.clicked.connect(self.reject)
        self.go_buttons = (b_later, b_start)
        brow = QHBoxLayout()
        brow.addStretch()
        for b in (b_later, b_start, b_cancel):
            brow.addWidget(b)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(brow)

        name = sanitize_filename(suggested) if suggested else (filename_from_url(url) or "download")
        self._set_name(name)
        self.path_edit.textEdited.connect(lambda _: setattr(self, "user_edited", True))
        self.cat.currentIndexChanged.connect(self._cat_changed)

        self.bridge = Bridge()
        self.bridge.probed.connect(self._on_probe)
        self.bridge.hls.connect(self._on_hls)
        self.bridge.video.connect(self._on_video)
        self.quality.currentIndexChanged.connect(self._quality_changed)
        if video_info:
            self._on_video(video_info, None)
            i = next((i for i in range(self.quality.count())
                      if self.quality.itemData(i).get("format") == preselect), -1)
            if i >= 0:
                self.quality.setCurrentIndex(i)
        elif ytdlp.is_youtube(url):
            self._start_video()
        elif hls.is_hls(url):
            self._start_hls()
        elif is_dash(url):
            self._start_video()  # DASH (.mpd): yt-dlp akışı indirip birleştirir
        else:
            threading.Thread(target=self._probe, daemon=True).start()

    # ---- Site videosu (YouTube vb.) — yt-dlp
    def _start_video(self, fallback_info=None):
        if not ytdlp.available():
            self.size_lbl.setText("Site videoları için gereken yt-dlp bulunamadı.")
            return
        self._fallback = fallback_info
        self.size_lbl.setText("Video inceleniyor…" if ytdlp.is_youtube(self.url)
                              else "Sayfadaki video aranıyor…")

        def work():
            try:
                self.bridge.video.emit(ytdlp.inspect(self.url, self.mgr.ffmpeg(), self.cookies, self.headers), None)
            except Exception as e:  # noqa: BLE001
                self.bridge.video.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_video(self, info, err):
        if err or not info or not info["choices"]:
            fb = getattr(self, "_fallback", None)
            if fb:  # video yok: normal sayfa/dosya olarak indir
                self._apply_probe(fb)
            else:
                self.size_lbl.setText(f"Video bilgisi alınamadı: {err or 'indirilebilir biçim yok'}")
            return
        self.video_info = info
        self._update_format_row()
        self.quality.blockSignals(True)
        self.quality.clear()
        default = 0
        for i, c in enumerate(info["choices"]):
            self.quality.addItem(c["label"], c)
            if c.get("height") and c["height"] <= 1080 and default == 0 and info["choices"][0]["height"] > 1080:
                default = i  # varsayılan: 1080p ya da altındaki en iyi kalite (her oynatıcıda açılır)
        pre = getattr(self, "_preselect", None)  # tarayıcı menüsünde seçilen kalite
        if pre:
            default = next((i for i, c in enumerate(info["choices"]) if c["format"] == pre), default)
        self.quality.setCurrentIndex(default)
        self.quality.blockSignals(False)
        self.form.setRowVisible(self.quality, True)
        self._quality_changed()

    def _quality_changed(self):
        if not self.video_info:
            return
        c = self.quality.currentData()
        text = f"Video  ·  {self.video_info['title']}"
        if self.video_info.get("duration"):
            text += f"  ·  süre {fmt_time(self.video_info['duration'])}"
        if c.get("size"):
            text += f"  ·  ≈ {fmt_size(c['size'])}"
        self.size_lbl.setText(text)
        self._set_name(sanitize_filename(self.video_info["title"]) + "." + c.get("ext", "mp4"))

    # ---- HLS (m3u8) video akışı
    def _start_hls(self):
        self.size_lbl.setText("Video akışı inceleniyor…")

        def work():
            try:
                self.bridge.hls.emit(hls.inspect(self.url, self.headers), None)
            except Exception as e:  # noqa: BLE001
                self.bridge.hls.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_hls(self, info, err):
        if err:
            self.size_lbl.setText(f"Video akışı okunamadı: {err}")
            return
        if info.get("live"):
            self.size_lbl.setText("Bu bir canlı yayın; canlı yayınlar desteklenmiyor.")
            return
        self.hls_info = info
        self._update_format_row()
        self.quality.clear()
        for v in info["variants"]:
            self.quality.addItem(hls.variant_label(v), v)
        self.form.setRowVisible(self.quality, len(info["variants"]) > 1)
        text = "HLS video akışı"
        if info.get("duration"):
            text += f"  ·  süre {fmt_time(info['duration'])}"
        if not self.mgr.ffmpeg():
            text += "  ·  ffmpeg bulunamadı: .ts olarak kaydedilir (Seçenekler → Video)"
        self.size_lbl.setText(text)
        stem = os.path.splitext(getattr(self, "name", "") or "")[0]
        if not stem or stem.lower() in ("index", "master", "playlist", "chunklist", "download"):
            stem = "video"
        self._set_name(stem + ".mp4")

    def _update_format_row(self):
        cat = self.cat.currentData()
        show = bool(self.video_info or self.hls_info or cat in ("video", "music"))
        self.form.setRowVisible(self.fmt, show)

    def _set_name(self, name):
        """Dosya adı arka planda tutulur (videonun başlığı / sunucunun verdiği ad); alanda yalnızca klasör görünür.
        Klasör, kullanıcı elle seçmediyse kategoriye göre belirlenir."""
        self.name = name
        cat = category_for(name)
        self.cat.blockSignals(True)
        self.cat.setCurrentIndex(max(0, self.cat.findData(cat)))
        self.cat.blockSignals(False)
        if not self.user_edited:
            self.path_edit.setText(self.mgr.category_dir(cat))
        self.path_edit.setToolTip(name)
        if hasattr(self, "form"):
            self._update_format_row()

    def _cat_changed(self):
        self.path_edit.setText(self.mgr.category_dir(self.cat.currentData()))
        self.user_edited = False

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Kayıt klasörü", self.path_edit.text())
        if d:
            self.path_edit.setText(os.path.normpath(d))
            self.user_edited = True

    def _probe(self):
        try:
            self.bridge.probed.emit(probe(self.url, self.headers), None)
        except Exception as e:  # noqa: BLE001
            self.bridge.probed.emit(None, str(e))

    def _on_probe(self, info, err):
        if err:
            self.size_lbl.setText(f"Sorgulanamadı: {err}")
            return
        if looks_like_torrent(self.url, info):
            self._start_torrent(info["final_url"])
            return
        if hls.is_hls(info["final_url"], info["content_type"]):
            self.url = info["final_url"]
            self._start_hls()
            return
        if is_dash(info["final_url"], info["content_type"]) and ytdlp.available():
            self.url = info["final_url"]
            self._start_video()
            return
        if (info.get("content_type") or "").startswith("text/html") and ytdlp.available():
            # Bir web sayfası: içinde indirilebilir video var mı? (IDM'deki gibi)
            self._start_video(fallback_info=info)
            return
        self._apply_probe(info)

    # ---- .torrent bağlantısı: dosya olarak kaydetmek yerine torrent olarak aç (dosya seçimi penceresi)
    def _start_torrent(self, url):
        self.size_lbl.setText("Torrent dosyası alınıyor…")
        for b in self.go_buttons:
            b.setEnabled(False)
        self.bridge.done.connect(self._on_torrent)

        def work():
            try:
                data = fetch_torrent(url, self.headers)
                import hashlib
                folder = os.path.join(TORRENT_DIR, "gelen")
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, hashlib.sha1(data).hexdigest() + ".torrent")
                with open(path, "wb") as f:
                    f.write(data)
                self.bridge.done.emit(path, None)
            except Exception as e:  # noqa: BLE001
                self.bridge.done.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_torrent(self, path, err):
        if err:
            self.size_lbl.setText(err)
            return
        self.accept()
        self.win.add_source(path)

    def _apply_probe(self, info):
        self.info = info
        res = "Evet" if info["resumable"] else "Hayır"
        self.size_lbl.setText(f"{fmt_size(info['size'])}   ·   Devam ettirme desteği: {res}")
        self._set_name(info["filename"])

    def _go(self, start):
        folder = self.path_edit.text().strip()
        if not folder:
            return
        path = os.path.join(folder, getattr(self, "name", "") or "download")
        fmt = self.fmt.currentData() if self.form.isRowVisible(self.fmt) else ""
        it = self._create(path, start)
        if fmt:
            it.extra["convert"] = fmt  # indirme bitince ffmpeg ile dönüştürülür
        if start:
            self.win.show_progress(it.id)
        self.win.refresh(force=True)
        self.accept()

    def _create(self, path, start):
        if self.video_info:
            return self.mgr.add_ytdlp(self.url_edit.text().strip(), path, self.quality.currentData(),
                                      self.video_info["title"], self.headers, self.cookies,
                                      self.desc.text(), start)
        if self.hls_info:
            v = self.quality.currentData()
            return self.mgr.add_hls(self.url_edit.text().strip(), v["url"], v.get("audio_url"), path,
                                    self.headers, self.desc.text(), start)
        return self.mgr.add_http(self.url_edit.text().strip(), path, self.cat.currentData(),
                                 self.headers, self.desc.text(), start,
                                 self.info.get("size"), self.info.get("resumable", True))


# ------------------------------------------------------------------ torrent ekleme
class TorrentAddDialog(QDialog):
    """Torrent ekleme: dosya listesi (onay kutulu ağaç) ile hangi dosyaların ineceği seçilir.
    Magnet'lerde önce meta veri (dosya listesi) eşlerden alınır; bu sırada hiçbir dosya inmez."""

    def __init__(self, win, source):
        super().__init__(win)
        self.win, self.mgr, self.source = win, win.mgr, source
        self.ti, self.probe_key = None, None
        self.setWindowTitle("Torrent Ekle")
        self.resize(640, 520)
        self.setAttribute(Qt.WA_DeleteOnClose)

        form = QFormLayout()
        src = QLabel(source if len(source) < 90 else source[:87] + "…")
        src.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Kaynak:", src)
        self.name_lbl = QLabel()
        self.size_lbl = QLabel()
        form.addRow("Ad:", self.name_lbl)
        form.addRow("Seçilen boyut:", self.size_lbl)
        self.dir_edit = QLineEdit(self.mgr.category_dir("torrent"))
        browse = QPushButton("…")
        browse.setObjectName("browse")
        browse.setFixedWidth(32)
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.dir_edit)
        row.addWidget(browse)
        form.addRow("Kayıt klasörü:", row)
        self.desc = QLineEdit()
        form.addRow("Açıklama:", self.desc)

        self.files = TorrentFilesTree()
        self.files.changed.connect(self._update_size)
        sel = QHBoxLayout()
        for text, on in (("Tümünü seç", True), ("Hiçbirini seçme", False)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, v=on: self.files.set_all(v))
            sel.addWidget(b)
        sel.addStretch()

        brow = QHBoxLayout()
        brow.addStretch()
        self.buttons = []
        for text, start in (("Sonra İndir", False), ("İndirmeyi Başlat", True)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=start: self._go(s))
            brow.addWidget(b)
            self.buttons.append(b)
        self.buttons[1].setDefault(True)
        c = QPushButton("İptal")
        c.clicked.connect(self.reject)
        brow.addWidget(c)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("İndirilecek dosyalar:"))
        lay.addWidget(self.files, 1)
        lay.addLayout(sel)
        lay.addLayout(brow)

        if is_magnet(source):
            dn = urllib.parse.parse_qs(urllib.parse.urlparse(source).query).get("dn")
            self.name_lbl.setText((dn[0] + " — " if dn else "") + "dosya listesi eşlerden alınıyor…")
            try:
                self.probe_key = self.mgr.torrents.probe_start(source, self.dir_edit.text())
            except Exception as e:  # noqa: BLE001
                self.name_lbl.setText(f"Hata: {e}")
                for b in self.buttons:
                    b.setEnabled(False)
                return
            self.poll = QTimer(self, interval=500, timeout=self._poll)
            self.poll.start()
        else:
            try:
                self._set_ti(tmod.lt.torrent_info(source))
            except Exception as e:  # noqa: BLE001
                self.name_lbl.setText(f"Torrent dosyası okunamadı: {e}")
                for b in self.buttons:
                    b.setEnabled(False)

    def _poll(self):
        ti = self.mgr.torrents.probe_info(self.probe_key) if self.probe_key else None
        if ti:
            self.poll.stop()
            self._set_ti(ti)

    def _set_ti(self, ti):
        self.ti = ti
        files = tmod.file_list(ti)
        self.name_lbl.setText(f"{ti.name()}   ({sum(1 for f in files if not f[2])} dosya)")
        self.files.populate(files)
        self._update_size()

    def _update_size(self):
        if self.ti:
            self.size_lbl.setText(f"{fmt_size(self.files.selected_size())} / {fmt_size(self.ti.total_size())}")

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Kayıt klasörü", self.dir_edit.text())
        if d:
            self.dir_edit.setText(os.path.normpath(d))

    def _go(self, start):
        pr = self.files.priorities() if self.ti else None
        if pr is not None and not self.files.any_selected():
            QMessageBox.warning(self, APP_NAME, "En az bir dosya seçmelisiniz.")
            return
        if pr is not None and all(leaf.checkState(0) == Qt.Checked for leaf, _ in self.files.leaves):
            pr = None
        try:
            os.makedirs(self.dir_edit.text(), exist_ok=True)
            it = self.mgr.add_torrent(self.source, self.dir_edit.text(), start, self.desc.text(),
                                      priorities=pr, probe_key=self.probe_key)
            self.probe_key = None  # oturum indirmeye devredildi
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_NAME, f"Torrent eklenemedi:\n{e}")
            return
        if start:
            self.win.show_progress(it.id)
        self.win.refresh(force=True)
        self.accept()

    def done(self, r):
        if self.probe_key:
            self.mgr.torrents.probe_cancel(self.probe_key)
            self.probe_key = None
        super().done(r)


# ------------------------------------------------------------------ indirme durumu
class ProgressDialog(QDialog):
    """IDM'deki indirme penceresi:
    üstte sekmeler (İndirme durumu · Hız sınırlayıcı · Bitince yapılacaklar), ortada düğmeler,
    altta (ayrıntılar) bağlantıların başlangıç noktaları ve ilerlemesi + bağlantı tablosu."""

    ON_COMPLETE_KEYS = (("show_dialog", "İndirme bitince 'Tamamlandı' penceresini göster"),
                        ("exit", "İndirme bitince TurboDM'den çık"),
                        ("sleep", "İndirme bitince bilgisayarı uyku moduna al"),
                        ("shutdown", "İndirme bitince bilgisayarı kapat"),
                        ("force", "Kapatırken açık programları zorla kapat"))

    def __init__(self, win, iid):
        # Sahipsiz (bağımsız) pencere: Windows'ta sahibi olan pencere, ana pencere simge durumuna
        # küçültülünce onunla birlikte iner. İndirme penceresi kendi başına açık kalsın.
        super().__init__(None)
        self.win, self.mgr, self.iid = win, win.mgr, iid
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(640)
        standalone_window(self)  # küçült / tam ekran / kapat + görev çubuğu düğmesi
        it = self.mgr.items[iid]
        self.kind = it.kind
        self.is_torrent = it.kind == "torrent"
        if not hasattr(it, "on_complete"):
            it.on_complete = {"show_dialog": self.mgr.settings["show_complete_dialog"]}

        # ---- sekme 1: İndirme durumu
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        self.lbl = {}
        rows = [("url", "Adres"), ("status", "Durum"), ("size", "Dosya boyutu"),
                ("done", "İndirilen"), ("speed", "Aktarım hızı"), ("eta", "Kalan süre")]
        if self.is_torrent:
            rows += [("peers", "Eşler / Seed"), ("upload", "Yükleme")]
        elif it.kind == "hls":
            rows += [("parts", "Video parçaları")]
        else:
            rows += [("resume", "Devam ettirme")]
        for r, (k, t) in enumerate(rows):
            grid.addWidget(QLabel(t), r, 0)
            self.lbl[k] = QLabel()
            self.lbl[k].setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(self.lbl[k], r, 1)
        grid.setColumnStretch(1, 1)
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 1000)
        self.pbar.setTextVisible(True)
        self.pbar.setMinimumHeight(22)
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.addLayout(grid)
        l1.addWidget(self.pbar)

        # ---- sekme 2: Hız sınırlayıcı
        t2 = QWidget()
        f2 = QFormLayout(t2)
        cur = int(it.extra.get("speed_limit_kb") or 0)
        self.lim_on = QCheckBox("Bu indirme için hız sınırı kullan")
        self.lim_on.setChecked(cur > 0)
        self.lim_kb = QSpinBox(minimum=1, maximum=10_000_000, value=cur or 1024, suffix=" KB/s")
        self.lim_kb.setEnabled(cur > 0)
        f2.addRow(self.lim_on)
        f2.addRow("En fazla:", self.lim_kb)
        note = QLabel("Genel hız sınırı (Seçenekler → Bağlantı) bundan bağımsız olarak tüm indirmelere uygulanır.")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        f2.addRow(note)
        self.lim_on.toggled.connect(self._limit_changed)
        self.lim_kb.valueChanged.connect(self._limit_changed)

        # ---- sekme 3: Bitince yapılacaklar
        t3 = QWidget()
        l3 = QVBoxLayout(t3)
        self.oc = {}
        for key, text in self.ON_COMPLETE_KEYS:
            cb = QCheckBox(text)
            cb.setChecked(bool(it.on_complete.get(key)))
            cb.toggled.connect(lambda v, k=key: self._on_complete_changed(k, v))
            self.oc[key] = cb
            l3.addWidget(cb)
        self.oc["force"].setEnabled(bool(it.on_complete.get("shutdown")))
        l3.addStretch()

        tabs = QTabWidget()
        tabs.addTab(t1, "İndirme durumu")
        if not self.is_torrent:
            tabs.addTab(t2, "Hız sınırlayıcı")
        tabs.addTab(t3, "Bitince yapılacaklar")

        # ---- düğmeler
        self.btn_details = QPushButton("<< Ayrıntıları gizle")
        self.btn_details.setAutoDefault(False)  # birincil (mavi) düğme Devam/Duraklat olsun
        self.btn_details.clicked.connect(self._toggle_details)
        self.btn_toggle = QPushButton()
        self.btn_toggle.setMinimumWidth(110)
        self.btn_toggle.setDefault(True)
        self.btn_toggle.clicked.connect(self._toggle)
        b_cancel = QPushButton("İptal")
        b_cancel.setAutoDefault(False)
        b_cancel.clicked.connect(self._cancel)
        brow = QHBoxLayout()
        brow.addWidget(self.btn_details)
        brow.addStretch()
        brow.addWidget(self.btn_toggle)
        brow.addWidget(b_cancel)

        # ---- ayrıntılar: bağlantılar (IDM'deki alt bölüm)
        self.details = QWidget()
        ld = QVBoxLayout(self.details)
        ld.setContentsMargins(0, 4, 0, 0)
        cap = QLabel("Dosyalar ve indirme ilerlemesi" if self.is_torrent
                     else "Bağlantılara göre başlangıç noktaları ve indirme ilerlemesi")
        cap.setStyleSheet("font-weight: 600;")
        ld.addWidget(cap)
        self.bar = SegmentBar()
        self.bar.setMinimumHeight(26)
        ld.addWidget(self.bar)
        if self.is_torrent:
            self.table = TorrentFilesTree(with_progress=True)
            self.table.changed.connect(self._priorities_changed)
            self._files_built = False
        else:
            self.table = QTableWidget(0, 3)
            self.table.setHorizontalHeaderLabels(["N.", "İndirilen", "Bilgi"])
            hh = self.table.horizontalHeader()
            hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            hh.setSectionResizeMode(2, QHeaderView.Stretch)
            self.table.verticalHeader().hide()
            self.table.verticalHeader().setDefaultSectionSize(22)
            self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.table.setSelectionMode(QAbstractItemView.NoSelection)
            self.table.setAlternatingRowColors(True)
            self.table.setShowGrid(False)
        self.table.setMinimumHeight(170)
        ld.addWidget(self.table, 1)

        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addLayout(brow)
        lay.addWidget(self.details, 1)
        self.resize(680, 600)

        self.timer = QTimer(self, interval=500, timeout=self.update_view)
        self.timer.start()
        self.update_view()

    # ---- olaylar
    def _toggle_details(self):
        show = not self.details.isVisible()
        self.details.setVisible(show)
        self.btn_details.setText("<< Ayrıntıları gizle" if show else "Ayrıntıları göster >>")
        self.adjustSize()

    def _limit_changed(self):
        self.lim_kb.setEnabled(self.lim_on.isChecked())
        self.mgr.set_item_limit(self.iid, self.lim_kb.value() if self.lim_on.isChecked() else 0)

    def _on_complete_changed(self, key, value):
        it = self.mgr.items.get(self.iid)
        if not it:
            return
        it.on_complete[key] = value
        if key in ("shutdown", "sleep") and value:  # ikisi birden olmaz
            other = "sleep" if key == "shutdown" else "shutdown"
            self.oc[other].setChecked(False)
        if key == "shutdown":
            self.oc["force"].setEnabled(value)

    def _toggle(self):
        it = self.mgr.items.get(self.iid)
        if not it:
            return
        if it.status in ("downloading", "connecting", "seeding"):
            self.mgr.stop(self.iid)
        else:
            self.mgr.start(self.iid)

    def _cancel(self):
        self.mgr.stop(self.iid)
        self.close()

    def _priorities_changed(self):
        pr = self.table.priorities()
        if self.table.any_selected():
            self.mgr.set_torrent_priorities(self.iid, pr)

    # ---- güncelleme
    def update_view(self):
        it = self.mgr.items.get(self.iid)
        if not it:
            self.close()
            return
        pct = min(100.0, (it.done_bytes / it.size * 100) if it.size else 0)
        self.setWindowTitle(f"%{pct:.0f} {it.filename}")
        self.lbl["url"].setText(it.url if len(it.url) < 80 else it.url[:77] + "…")
        st = STATUS_TEXT.get(it.status, it.status)
        if it.error:
            st += f" — {it.error}"
        self.lbl["status"].setText(st)
        approx = "≈ " if it.kind in ("hls", "ytdlp") and it.status != "completed" and it.size else ""
        self.lbl["size"].setText(approx + fmt_size(it.size))
        self.lbl["done"].setText(f"{fmt_size(it.done_bytes)}  (%{pct:.2f})")
        self.lbl["speed"].setText(fmt_speed(it.speed) or "—")
        self.lbl["eta"].setText(fmt_time(it.eta()) or "—")
        self.pbar.setValue(int(pct * 10))
        self.pbar.setFormat(f"%{pct:.1f}")
        running = it.status in ("downloading", "connecting", "seeding")
        self.btn_toggle.setText("Duraklat" if running else "Devam Et")

        if self.is_torrent:
            self.lbl["peers"].setText(f"{it.peers} / {it.seeds}")
            self.lbl["upload"].setText(fmt_speed(it.ul_speed) or "—")
            self.bar.set_data(it.size, [[0, (it.size or 1) - 1, it.done_bytes]])
            files = self.mgr.torrents.files(it.id) if self.mgr.torrents else []
            if files and not self._files_built:
                self.table.populate([(p, s, pad) for p, s, pad, _ in files], it.extra.get("priorities"))
                self._files_built = True
            if files:
                self.table.set_progress([d for *_, d in files])
            return

        if it.task:
            total, segs = it.task.bar_data()
        elif it.status == "completed":
            total, segs = 1, [[0, 0, 1]]
        elif it.kind == "hls":
            total, segs = 1, [[0, 0, (it.done_bytes / it.size) if it.size else 0]]
        else:
            total, segs = it.size, [list(s) for s in it.segments]
        self.bar.set_data(total, segs)
        if it.kind == "hls":
            n_done, n_total = len(it.extra.get("done", [])), it.extra.get("total")
            self.lbl["parts"].setText(f"{n_done} / {n_total}" if n_total else "—")
        else:
            txt = "Evet" if it.resumable else "Hayır"
            lim = it.extra.get("server_conn_limit") if isinstance(it.extra, dict) else None
            if lim and lim < it.connections:
                txt += f"   ·   Sunucu en fazla {lim} bağlantıya izin veriyor"
            self.lbl["resume"].setText(txt)
        conns = it.task.connections_snapshot() if it.task else []
        self.table.setRowCount(len(conns))
        for r, (n, done, total, info) in enumerate(conns):
            amount = f"{fmt_size(done)} / {fmt_size(total)}" if total else fmt_size(done)
            for c, v in enumerate((str(n), amount, info)):
                cell = self.table.item(r, c)
                if cell is None:
                    cell = QTableWidgetItem()
                    self.table.setItem(r, c, cell)
                if cell.text() != v:
                    cell.setText(v)
            color = (QColor(theme.T["ok"]) if "alınıyor" in info else QColor(theme.T["bad"]) if "Hata" in info
                     else QColor())
            self.table.item(r, 2).setForeground(color if color.isValid() else self.palette().text().color())
        if it.status == "completed":
            self.close()


# ------------------------------------------------------------------ bitince yapılacaklar
POWER_ACTIONS = {"shutdown": "Bilgisayar kapatılacak", "sleep": "Bilgisayar uyku moduna alınacak",
                 "exit": "TurboDM kapatılacak"}


class PowerActionDialog(QDialog):
    """İndirme / kuyruk bitince yapılacak işlem: geri sayım, 'Şimdi' ve 'İptal' (IDM gibi)."""

    def __init__(self, win, action, force=False, seconds=30, reason="İndirme tamamlandı."):
        super().__init__(win)
        self.win, self.action, self.force, self.left = win, action, force, seconds
        self.setWindowTitle(APP_NAME)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(420)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self.reason = reason
        b_now = QPushButton("Şimdi")
        b_now.clicked.connect(self._do)
        b_cancel = QPushButton("İptal")
        b_cancel.setDefault(True)
        b_cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(b_now)
        row.addWidget(b_cancel)
        lay = QVBoxLayout(self)
        lay.addWidget(self.msg)
        lay.addLayout(row)
        self.timer = QTimer(self, interval=1000, timeout=self._tick)
        self.timer.start()
        self._tick(first=True)

    def _tick(self, first=False):
        if not first:
            self.left -= 1
        if self.left <= 0:
            self._do()
            return
        self.msg.setText(f"<b>{self.reason}</b><br><br>{POWER_ACTIONS[self.action]}: "
                         f"<b>{self.left}</b> saniye.<br>Vazgeçmek için İptal'e basın.")

    def _do(self):
        self.timer.stop()
        self.accept()
        self.win.perform_power_action(self.action, self.force)


# ------------------------------------------------------------------ ayarlar
class OptionsDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.mgr = win.mgr
        s = self.mgr.settings
        self.setWindowTitle("Seçenekler")
        self.setMinimumWidth(560)
        tabs = QTabWidget()

        g = QWidget()
        f = QFormLayout(g)
        self.root = QLineEdit(s["download_root"])
        row = self._with_browse(self.root, lambda: QFileDialog.getExistingDirectory(
            self, "Ana indirme klasörü", self.root.text()))
        f.addRow("Ana indirme klasörü:", row)
        self.clip = QCheckBox("Panoya kopyalanan indirme adreslerini yakala")
        self.clip.setChecked(s["clipboard_monitor"])
        f.addRow(self.clip)
        self.complete = QCheckBox("İndirme bitince 'Tamamlandı' penceresini göster")
        self.complete.setChecked(s["show_complete_dialog"])
        f.addRow(self.complete)
        self.autostart = QCheckBox("Windows açılışında başlat (sistem tepsisinde)")
        self.autostart.setChecked(winassoc.autostart_enabled())
        f.addRow(self.autostart)
        self.autoupd = QCheckBox("Açılışta güncellemeleri denetle (günde bir kez)")
        self.autoupd.setChecked(s.get("auto_update_check", True))
        f.addRow(self.autoupd)
        self.theme = QComboBox()
        for text, key in (("Windows ile aynı (otomatik)", "auto"), ("Açık", "light"), ("Koyu", "dark")):
            self.theme.addItem(text, key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(s.get("theme", "auto"))))
        self.theme.currentIndexChanged.connect(  # seçince hemen önizleme
            lambda: theme.apply(QApplication.instance(), self.theme.currentData()))
        self._theme_before = s.get("theme", "auto")
        self.rejected.connect(lambda: theme.apply(QApplication.instance(), self._theme_before))
        f.addRow("Tema:", self.theme)
        self.port = QSpinBox(maximum=65535, minimum=1024, value=s["server_port"])
        f.addRow("Tarayıcı entegrasyon portu:", self.port)
        tabs.addTab(g, "Genel")

        c = QWidget()
        f = QFormLayout(c)
        self.conns = QSpinBox(minimum=1, maximum=32, value=s["connections"])
        f.addRow("İndirme başına bağlantı:", self.conns)
        self.maxc = QSpinBox(minimum=1, maximum=20, value=s["max_concurrent"])
        f.addRow("Kuyrukta aynı anda indirme:", self.maxc)
        self.limit = QSpinBox(minimum=0, maximum=10_000_000, value=s["speed_limit_kb"], suffix=" KB/s")
        self.limit.setSpecialValueText("Sınırsız")
        f.addRow("Hız sınırı (toplam):", self.limit)
        tabs.addTab(c, "Bağlantı")

        v = QWidget()
        f = QFormLayout(v)
        self.ffmpeg = QLineEdit(s.get("ffmpeg_path", ""))
        self.ffmpeg.setPlaceholderText("Boş bırakılırsa PATH'te aranır")
        f.addRow("ffmpeg.exe:", self._with_browse(self.ffmpeg, lambda: QFileDialog.getOpenFileName(
            self, "ffmpeg.exe", "", "ffmpeg (ffmpeg.exe)")[0]))
        self.ff_status = QLabel()
        self.ff_status.setWordWrap(True)
        f.addRow(self.ff_status)
        self.ffmpeg.textChanged.connect(self._ff_status)
        self._ff_status()
        yt = QLabel("Video motoru: " + ("hazır" if ytdlp.version() else "bulunamadı")
                    + ("" if ytdlp.deno_path() else "  ·  ⚠ bazı sitelerde kısıtlı çalışır"))
        yt.setWordWrap(True)
        f.addRow(yt)
        b = QPushButton("Video motorunu güncelle…")
        b.clicked.connect(lambda: (self.accept(), self.parent().check_updates()))
        f.addRow(b)
        tabs.addTab(v, "Video")

        t = QWidget()
        f = QFormLayout(t)
        self.tport = QSpinBox(minimum=1024, maximum=65535, value=s["torrent_port"])
        f.addRow("Dinleme portu:", self.tport)
        self.ul = QSpinBox(minimum=0, maximum=10_000_000, value=s["torrent_upload_kb"], suffix=" KB/s")
        self.ul.setSpecialValueText("Sınırsız / otomatik")
        f.addRow("Yükleme sınırı:", self.ul)
        self.ulauto = QCheckBox("İndirirken yükleme hızını otomatik sınırla (önerilen: indirme hızlanır)")
        self.ulauto.setToolTip("Yükleme hattı dolunca indirme de yavaşlar. Açıkken, torrent inerken yükleme hızı\n"
                               "indirme hızına göre ayarlanır (150 KB/s – 2 MB/s). Elle bir sınır girerseniz o geçerlidir.")
        self.ulauto.setChecked(s["torrent_upload_auto"])
        f.addRow(self.ulauto)
        self.seed = QCheckBox("İndirme bitince paylaşmaya (seed) devam et")
        self.seed.setChecked(s["seed_after_complete"])
        f.addRow(self.seed)
        f.addRow(QLabel("Torrent motoru: " + ("hazır (libtorrent " + tmod.lt.__version__ + ")"
                                              if self.mgr.torrents else f"yok — {self.mgr.torrent_error}")))
        self.assoc_lbl = QLabel()
        self.assoc_lbl.setWordWrap(True)
        f.addRow(self.assoc_lbl)
        arow = QHBoxLayout()
        for text, fn in (("Magnet ve .torrent'i TurboDM ile aç", self._register),
                         ("İlişkilendirmeyi kaldır", self._unregister),
                         ("Varsayılan uygulamalar…", winassoc.open_default_apps)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            arow.addWidget(b)
        f.addRow(arow)
        self._assoc_status()
        tabs.addTab(t, "Torrent")

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(bb)

    def _with_browse(self, edit, picker):
        b = QPushButton("…")
        b.setObjectName("browse")
        b.setFixedWidth(32)

        def pick():
            p = picker()
            if p:
                edit.setText(os.path.normpath(p))
        b.clicked.connect(pick)
        row = QHBoxLayout()
        row.addWidget(edit)
        row.addWidget(b)
        return row

    def _ff_status(self):
        ff = hls.find_ffmpeg(self.ffmpeg.text().strip())
        self.ff_status.setText(
            f"✔ ffmpeg bulundu: {ff}\nHLS videoları .mp4 olarak kaydedilir, ayrı ses kanalı birleştirilir." if ff else
            "✖ ffmpeg bulunamadı. HLS videoları yine iner ama .ts olarak kaydedilir; ayrı ses kanalı "
            "varsa ayrı dosyaya yazılır.\nKurmak için: winget install Gyan.FFmpeg")

    def _assoc_status(self):
        if winassoc.is_registered():
            txt = "✔ magnet bağlantıları ve .torrent dosyaları TurboDM ile açılıyor."
            other = winassoc.user_choice_overrides()
            if other:
                txt = (f"⚠ Kayıt yapıldı ama Windows'ta varsayılan magnet uygulaması hâlâ '{other}'. "
                       "'Varsayılan uygulamalar…' ile TurboDM'i seçin.")
        else:
            txt = "magnet bağlantıları ve .torrent dosyaları henüz TurboDM ile ilişkilendirilmedi."
        self.assoc_lbl.setText(txt)

    def _register(self):
        try:
            winassoc.register()
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, f"Kayıt yapılamadı: {e}")
        self._assoc_status()

    def _unregister(self):
        winassoc.unregister()
        self._assoc_status()

    def _save(self):
        s = self.mgr.settings
        restart = s["server_port"] != self.port.value() or s["torrent_port"] != self.tport.value()
        s.update(download_root=self.root.text(), clipboard_monitor=self.clip.isChecked(),
                 show_complete_dialog=self.complete.isChecked(), server_port=self.port.value(),
                 connections=self.conns.value(), max_concurrent=self.maxc.value(),
                 speed_limit_kb=self.limit.value(), torrent_port=self.tport.value(),
                 torrent_upload_kb=self.ul.value(), seed_after_complete=self.seed.isChecked(),
                 torrent_upload_auto=self.ulauto.isChecked(), theme=self.theme.currentData(),
                 ffmpeg_path=self.ffmpeg.text().strip(), auto_update_check=self.autoupd.isChecked())
        self.mgr.apply_settings()
        if self.autostart.isChecked() != winassoc.autostart_enabled():
            winassoc.set_autostart(self.autostart.isChecked())
        if restart:
            QMessageBox.information(self, APP_NAME, "Port değişiklikleri program yeniden başlatılınca geçerli olur.")
        self.accept()


class SchedulerDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.mgr = win.mgr
        s = self.mgr.settings
        self.setWindowTitle("Zamanlayıcı")
        f = QFormLayout()
        self.enabled = QCheckBox("Kuyruğu belirtilen saatte otomatik başlat/durdur")
        self.enabled.setChecked(s["schedule_enabled"])
        f.addRow(self.enabled)
        self.start = QTimeEdit(QTime.fromString(s["schedule_start"], "HH:mm"))
        self.stop = QTimeEdit(QTime.fromString(s["schedule_stop"], "HH:mm"))
        for w in (self.start, self.stop):
            w.setDisplayFormat("HH:mm")
        f.addRow("Başlama saati:", self.start)
        f.addRow("Durma saati:", self.stop)
        self.maxc = QSpinBox(minimum=1, maximum=20, value=s["max_concurrent"])
        f.addRow("Aynı anda indirme:", self.maxc)
        self.qdone = QComboBox()
        for key, text in (("none", "Hiçbir şey yapma"), ("shutdown", "Bilgisayarı kapat"),
                          ("sleep", "Bilgisayarı uyku moduna al"), ("exit", "TurboDM'den çık")):
            self.qdone.addItem(text, key)
        self.qdone.setCurrentIndex(max(0, self.qdone.findData(s.get("queue_done_action", "none"))))
        f.addRow("Kuyruk bitince:", self.qdone)
        self.qforce = QCheckBox("Kapatırken açık programları zorla kapat")
        self.qforce.setChecked(s.get("queue_done_force", False))
        f.addRow(self.qforce)
        n = sum(1 for i in self.mgr.items.values() if i.in_queue)
        f.addRow(QLabel(f"Kuyruktaki dosya sayısı: {n}"))
        b_now = QPushButton("Kuyruğu Şimdi Başlat")
        b_now.clicked.connect(lambda: (self._save(), self.mgr.start_queue(), self.accept()))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(lambda: (self._save(), self.accept()))
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(f)
        row = QHBoxLayout()
        row.addWidget(b_now)
        row.addStretch()
        row.addWidget(bb)
        lay.addLayout(row)

    def _save(self):
        self.mgr.settings.update(schedule_enabled=self.enabled.isChecked(),
                                 schedule_start=self.start.time().toString("HH:mm"),
                                 schedule_stop=self.stop.time().toString("HH:mm"),
                                 max_concurrent=self.maxc.value(),
                                 queue_done_action=self.qdone.currentData(),
                                 queue_done_force=self.qforce.isChecked())
        self.mgr.apply_settings()


# ------------------------------------------------------------------ güncellemeler
class UpdateDialog(QDialog):
    """Yardım → Güncellemeleri denetle: TurboDM'in kendisi + YouTube motoru (yt-dlp)."""

    def __init__(self, win, prefetched=None):
        super().__init__(win)
        self.win, self.mgr = win, win.mgr
        self.info = None
        self._cancel = False
        self.setWindowTitle("Güncellemeleri Denetle")
        self.setMinimumWidth(540)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # --- TurboDM
        self.app_lbl = QLabel("TurboDM sürümü denetleniyor…")
        self.app_lbl.setWordWrap(True)
        self.notes = QTextBrowser()
        self.notes.setMaximumHeight(150)
        self.notes.hide()
        self.app_bar = QProgressBar()
        self.app_bar.hide()
        self.app_btn = QPushButton("İndir ve Kur")
        self.app_btn.hide()
        self.app_btn.clicked.connect(self._install)
        g1 = QGroupBox(f"TurboDM  (kurulu: {VERSION})")
        l1 = QVBoxLayout(g1)
        l1.addWidget(self.app_lbl)
        l1.addWidget(self.notes)
        l1.addWidget(self.app_bar)
        r1 = QHBoxLayout()
        r1.addStretch()
        r1.addWidget(self.app_btn)
        l1.addLayout(r1)

        # --- yt-dlp
        self.yt_lbl = QLabel("Video motoru denetleniyor…")
        self.yt_lbl.setWordWrap(True)
        self.yt_btn = QPushButton("Video motorunu güncelle")
        self.yt_btn.hide()
        self.yt_btn.clicked.connect(self._update_ytdlp)
        g2 = QGroupBox("Video motoru")
        l2 = QVBoxLayout(g2)
        l2.addWidget(self.yt_lbl)
        r2 = QHBoxLayout()
        r2.addStretch()
        r2.addWidget(self.yt_btn)
        l2.addLayout(r2)

        close = QPushButton("Kapat")
        close.clicked.connect(self.close)
        lay = QVBoxLayout(self)
        lay.addWidget(g1)
        lay.addWidget(g2)
        rb = QHBoxLayout()
        rb.addStretch()
        rb.addWidget(close)
        lay.addLayout(rb)

        self.b_app, self.b_yt = Bridge(), Bridge()
        self.b_app.done.connect(self._on_app)
        self.b_app.progress.connect(self._on_app_progress)
        self.b_yt.done.connect(self._on_yt)
        if prefetched:
            self._on_app(prefetched, None)
        else:
            self._run(self.b_app, self._check_app)
        self._run(self.b_yt, ytdlp.update_available)

    @staticmethod
    def _run(bridge, fn, *a):
        def work():
            try:
                bridge.done.emit(fn(*a), None)
            except Exception as e:  # noqa: BLE001
                bridge.done.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _check_app(self):
        url = updater.manifest_url(self.mgr.settings.get("update_repo") or None)
        if not url:
            raise RuntimeError("Güncelleme sunucusu ayarlanmamış.")
        return updater.check(url)

    # ---- TurboDM
    def _on_app(self, info, err):
        if err:
            if self.app_bar.isVisible():  # indirme sırasında
                self.app_bar.hide()
                self.app_btn.setEnabled(True)
                self.app_lbl.setText(f"Güncelleme başarısız: {err}")
            else:
                self.app_lbl.setText(f"Denetlenemedi: {err}")
            return
        if isinstance(info, str):  # indirme bitti → kurulum dosyasının yolu
            self.app_lbl.setText("Kurulum başlatılıyor… TurboDM, kurulum sırasında otomatik olarak kapanacak.")
            try:
                updater.run_installer(info)
            except OSError as e:
                self.app_lbl.setText(f"Kurulum başlatılamadı: {e}")
                self.app_btn.setEnabled(True)
            return
        self.info = info
        if not info["available"]:
            self.app_lbl.setText(f"✔ TurboDM güncel (sürüm {info['current']}).")
            return
        what = "aynı sürümün yeni bir derlemesi" if info["same_version"] else f"yeni sürüm {info['latest']}"
        when = f" · {info['published']}" if info.get("published") else ""
        size = f" · {fmt_size(info['size'])}" if info.get("size") else ""
        self.app_lbl.setText(f"<b>Güncelleme var:</b> {what}{when}{size}")
        if info.get("notes"):
            self.notes.setPlainText(info["notes"])
            self.notes.show()
        self.app_btn.show()

    def _install(self):
        self.app_btn.setEnabled(False)
        self.app_bar.show()
        self.app_bar.setRange(0, 0)
        self.app_lbl.setText("Kurulum dosyası indiriliyor ve doğrulanıyor…")
        self._run(self.b_app, updater.download, self.info,
                  lambda got, total: self.b_app.progress.emit(got, total), lambda: self._cancel)

    def _on_app_progress(self, got, total):
        if total:
            self.app_bar.setRange(0, 1000)
            self.app_bar.setValue(int(got / total * 1000))
        self.app_bar.setFormat(f"{fmt_size(got)} / {fmt_size(total)}" if total else fmt_size(got))

    # ---- yt-dlp
    def _on_yt(self, res, err):
        if err:
            self.yt_lbl.setText(f"Denetlenemedi: {err}")
            return
        if isinstance(res, str):  # güncelleme yapıldı
            self.yt_lbl.setText(f"✔ Video motoru güncellendi: {res}")
            self.yt_btn.hide()
            return
        cur, latest, avail = res
        if avail:
            self.yt_lbl.setText(f"Güncelleme var: kurulu {cur or '—'} → en son {latest}. Video siteleri değişiklik "
                                "yaptığında indirmeler bozulabilir; güncel tutmanız önerilir.")
            self.yt_btn.show()
        else:
            self.yt_lbl.setText(f"✔ Video motoru güncel ({cur}).")

    def _update_ytdlp(self):
        self.yt_btn.setEnabled(False)
        self.yt_lbl.setText("İndiriliyor ve doğrulanıyor…")
        self._run(self.b_yt, ytdlp.update)

    def closeEvent(self, e):
        self._cancel = True
        super().closeEvent(e)


# ------------------------------------------------------------------ ana pencere
COLUMNS = ["", "Dosya Adı", "Boyut", "Durum", "Kalan Süre", "Aktarım Hızı", "Son Deneme", "Açıklama"]
SEL = 0    # onay kutusu sütunu (toplu seçim)
NAME = 1
STATUS = 3
PROGRESS_ROLE = Qt.UserRole + 1   # durum hücresi: 0..1 ilerleme (yoksa None)
TONE_ROLE = Qt.UserRole + 2       # durum hücresi: renk (accent | ok | bad | muted)


COUNT_ROLE = Qt.UserRole + 2      # kenar çubuğu: kategorideki indirme sayısı


class NavDelegate(QStyledItemDelegate):
    """Kenar çubuğu: kategori adı + sağda soluk renkte indirme sayısı (aynı yuvarlatılmış satırda)."""

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width() + 30, max(s.height(), 34))  # ferah satırlar + sayı için yer

    def paint(self, p, option, index):
        super().paint(p, option, index)
        n = index.data(COUNT_ROLE)
        if n:
            p.save()
            sel = option.state & QStyle.State_Selected
            p.setPen(QColor(theme.T["accent_text"] if sel else theme.T["muted"]))
            p.drawText(option.rect.adjusted(0, 0, -10, 0), Qt.AlignRight | Qt.AlignVCenter, str(n))
            p.restore()


class StatusDelegate(QStyledItemDelegate):
    """Durum sütunu: yazının altında ince, yuvarlatılmış ilerleme çizgisi (inen, duraklatılmış indirmeler);
    tamamlanan yeşil, hatalı kırmızı yazılır. Renkler temaya göre."""

    def paint(self, p, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text, opt.text = opt.text, ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)  # zemin ve seçim
        frac = index.data(PROGRESS_ROLE)
        tone = index.data(TONE_ROLE) or "text"
        r = opt.rect.adjusted(8, 0, -8, 0)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        text_r = r.adjusted(0, -5 if frac is not None else 0, 0, -5 if frac is not None else 0)
        p.setPen(QColor(theme.T.get(tone, theme.T["text"])))
        p.setFont(opt.font)
        p.drawText(text_r, Qt.AlignVCenter | Qt.AlignLeft,
                   opt.fontMetrics.elidedText(text, Qt.ElideRight, text_r.width()))
        if frac is not None:
            track = QRectF(r.x(), r.bottom() - 8, r.width(), 4)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.T["track"]))
            p.drawRoundedRect(track, 2, 2)
            if frac > 0:
                done = QRectF(track.x(), track.y(), max(4.0, track.width() * min(1.0, frac)), track.height())
                p.setBrush(QColor(theme.T["accent"] if tone != "muted" else theme.T["muted"]))
                p.drawRoundedRect(done, 2, 2)
        p.restore()


class DownloadTable(QTableWidget):
    """İndirme listesi. Onay kutusu sütununa tıklamak satırı diğer seçimleri bozmadan seçime ekler/çıkarır
    (dokunmatik ekranda ve Ctrl tuşu bilmeyenler için toplu seçim); kutular seçimi gösterir."""

    def selectionCommand(self, index, event=None):
        from PySide6.QtCore import QEvent, QItemSelectionModel
        if (index.isValid() and index.column() == SEL and event is not None
                and event.type() == QEvent.MouseButtonPress):
            return QItemSelectionModel.Toggle | QItemSelectionModel.Rows
        return super().selectionCommand(index, event)


class MainWindow(QMainWindow):
    def __init__(self, mgr: Manager):
        super().__init__()
        self.mgr = mgr
        self.icon = load_icon()
        QApplication.setWindowIcon(self.icon)
        self.setWindowIcon(self.icon)
        self.setWindowTitle(f"{APP_NAME} — İnternet İndirme Yöneticisi")
        self.resize(1100, 620)
        self.setAcceptDrops(True)
        self.progress_dialogs = {}
        self._visible = []
        self._filter = "all"
        self._last_clip = ""
        self._quitting = False

        app = QApplication.instance()
        # kullanıcının seçtiği tema; pencere başlığı rengi ve yeni pencereleri ortalama da burada kurulur
        theme.install(app, mgr.settings.get("theme", "auto"))
        self._build_actions()
        self._build_ui()
        self._build_tray()
        theme.notifier.changed.connect(self._theme_changed)

        try:
            self._fmt_cache = {}
            server.handlers["/formats"] = self._formats_handler
            self.srv = server.start(mgr.settings["server_port"])
        except OSError as e:
            self.srv = None
            self.statusBar().showMessage(f"Tarayıcı köprüsü başlatılamadı: {e}", 10000)

        QApplication.clipboard().dataChanged.connect(self._on_clipboard)
        QTimer.singleShot(8000, self._auto_update_check)
        self.timer = QTimer(self, interval=500, timeout=self._tick)
        self.timer.start()
        self.refresh(force=True)

    # ---------------------------------------------------------- kurulum
    def _act(self, text, icon, slot, shortcut=None):
        """icon: theme.py'deki simge adı (tema değişince yeniden renklenir)."""
        a = QAction(theme.icon(icon) if icon else QIcon(), text, self)
        a.setProperty("tdm_icon", icon)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
        return a

    def _build_actions(self):
        self.a_add = self._act("URL Ekle", "add", self.add_url_prompt, "Ctrl+N")
        self.a_torrent = self._act("Torrent Ekle", "torrent", self.add_torrent_prompt, "Ctrl+T")
        self.a_magnet = self._act("Magnet Ekle", "magnet", self.add_magnet_prompt, "Ctrl+M")
        self.a_resume = self._act("Devam Et", "play", self.resume_selected)
        self.a_stop = self._act("Durdur", "pause", self.stop_selected)
        self.a_stop_all = self._act("Tümünü Durdur", "stop", self.mgr.stop_all)
        self.a_delete = self._act("Sil", "trash", lambda: self.delete_selected(False), "Del")
        self.a_delete_done = self._act("Bitenleri Sil", "trash_done", self.delete_completed)
        self.a_select_all = self._act("Tümünü seç", "finished", self.select_all, "Ctrl+A")
        self.a_select_none = self._act("Seçimi kaldır", None, lambda: self.table.clearSelection(), "Esc")
        self.a_options = self._act("Seçenekler", "settings", self.open_options)
        self.a_sched = self._act("Zamanlayıcı", "clock", lambda: SchedulerDialog(self).exec())
        self.a_qstart = self._act("Kuyruğu Başlat", "queue_start", self.mgr.start_queue)
        self.a_qstop = self._act("Kuyruğu Durdur", "queue_stop", self.mgr.stop_queue)
        self.a_quit = self._act("Çıkış", "quit", self.quit_app, "Ctrl+Q")
        self.a_update = self._act("Güncellemeleri denetle…", "refresh", self.check_updates)

    def _theme_changed(self):
        """Windows açık/koyu moda geçti ya da tema seçildi: simgeleri yeni renklerle yeniden çiz."""
        for a in self.findChildren(QAction):
            name = a.property("tdm_icon")
            if name:
                a.setIcon(theme.icon(name))
        self._brand_icon.setPixmap(self.icon.pixmap(30, 30))
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for it in [top] + [top.child(j) for j in range(top.childCount())]:
                it.setIcon(0, theme.icon(it.data(0, Qt.UserRole + 1)))
        for r in range(self.table.rowCount()):  # durum simgeleri yeniden
            cell = self.table.item(r, NAME)
            if cell:
                cell.setData(Qt.UserRole, None)
        self.refresh(force=True)
        if not self.mgr.torrents:
            self.a_torrent.setEnabled(False)
            self.a_magnet.setEnabled(False)

    def _build_ui(self):
        mb = self.menuBar()
        m = mb.addMenu("&Görevler")
        for a in (self.a_add, self.a_torrent, self.a_magnet):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_quit)
        m = mb.addMenu("&İndirmeler")
        for a in (self.a_resume, self.a_stop, self.a_stop_all, None, self.a_delete,
                  self.a_delete_done, None, self.a_qstart, self.a_qstop, self.a_sched, None, self.a_options):
            m.addSeparator() if a is None else m.addAction(a)
        m.addSeparator()
        self._add_select_menu(m.addMenu("Toplu seçim"))
        m = mb.addMenu("&Yardım")
        m.addAction(self.a_update)
        m.addSeparator()
        m.addAction("Hakkında", lambda: QMessageBox.about(
            self, APP_NAME, f"<b>{APP_NAME}</b> {VERSION}<br>Çok bağlantılı HTTP/HTTPS, FTP, HLS video, "
                            f"video ve BitTorrent indirme yöneticisi."))

        tb = QToolBar("Araçlar")
        tb.setObjectName("main")
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tb.setIconSize(QSize(26, 26))
        tb.setMovable(False)
        brand = QWidget()  # sol başta TurboDM logosu ve adı
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(4, 0, 12, 0)
        bl.setSpacing(8)
        self._brand_icon = QLabel()
        self._brand_icon.setPixmap(self.icon.pixmap(30, 30))
        name = QLabel("TurboDM")
        name.setObjectName("brand")
        bl.addWidget(self._brand_icon)
        bl.addWidget(name)
        tb.addWidget(brand)
        tb.addSeparator()
        for a in (self.a_add, self.a_torrent, self.a_magnet, None, self.a_resume, self.a_stop,
                  self.a_stop_all, None, self.a_delete, self.a_delete_done, None, self.a_options,
                  self.a_sched, self.a_qstart, self.a_qstop):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.addToolBar(tb)

        self.tree = QTreeWidget()
        self.tree.setObjectName("nav")
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(16)
        self.tree.setIconSize(QSize(18, 18))
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setItemDelegate(NavDelegate(self.tree))
        cat_icons = {"compressed": "compressed", "documents": "document", "music": "music",
                     "programs": "program", "video": "video", "torrent": "magnet", "general": "general"}

        def nav_item(text, key, ic):
            it = QTreeWidgetItem([text])
            it.setData(0, Qt.UserRole, key)
            it.setData(0, Qt.UserRole + 1, ic)
            it.setIcon(0, theme.icon(ic))
            return it
        root = nav_item("Tüm İndirmeler", "all", "all")
        for key, (disp, _, _) in CATEGORIES.items():
            root.addChild(nav_item(disp, "cat:" + key, cat_icons.get(key, "general")))
        self.tree.addTopLevelItem(root)
        for text, key, ic in (("Bitmemiş", "unfinished", "unfinished"), ("Bitmiş", "finished", "finished"),
                              ("Kuyruk", "queue", "queue")):
            self.tree.addTopLevelItem(nav_item(text, key, ic))
        self.tree.expandAll()
        self.tree.setItemsExpandable(False)
        self.tree.setCurrentItem(root)
        self.tree.currentItemChanged.connect(self._filter_changed)

        self.table = DownloadTable(0, len(COLUMNS))
        self.table.setObjectName("list")
        self.table.setItemDelegateForColumn(STATUS, StatusDelegate(self.table))
        self.table.setIconSize(QSize(18, 18))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeaderItem(SEL).setToolTip("Tümünü seç / seçimi kaldır")
        # başlığa tıklamak sütunu (satır seçiminde bütün listeyi) seçmesin; yalnızca kutu başlığı seçim yapar
        self.table.horizontalHeader().sectionPressed.disconnect()
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().sectionClicked.connect(
            lambda c: (self.table.clearSelection() if len(self.selected_ids()) == len(self._visible)
                       else self.select_all()) if c == SEL else None)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        for a in (self.a_select_all, self.a_select_none):  # kısayollar liste odaktayken çalışsın
            a.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            self.table.addAction(a)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(self._double_click)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(NAME, QHeaderView.Stretch)
        h.setSectionResizeMode(SEL, QHeaderView.Fixed)
        for c, w in ((SEL, 30), (2, 90), (3, 150), (4, 90), (5, 100), (6, 130), (7, 150)):
            self.table.setColumnWidth(c, w)

        split = QSplitter()
        split.addWidget(self.tree)
        split.addWidget(self.table)
        split.setSizes([210, 890])
        split.setHandleWidth(1)
        split.setChildrenCollapsible(False)
        self.setCentralWidget(split)
        self.sel_lbl = QLabel()
        self.statusBar().addPermanentWidget(self.sel_lbl)
        self.speed_lbl = QLabel()
        self.statusBar().addPermanentWidget(self.speed_lbl)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self.icon, self)
        menu = QMenu()
        menu.addAction("Göster", self.show_normal)
        menu.addAction(self.a_add)
        menu.addAction(self.a_stop_all)
        menu.addSeparator()
        menu.addAction(self.a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.show_normal() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def show_normal(self):
        bring_to_front(self)

    # ---------------------------------------------------------- liste
    def _filter_changed(self, cur, _prev):
        self._filter = cur.data(0, Qt.UserRole) if cur else "all"
        self.refresh(force=True)

    def _match(self, it):
        f = self._filter
        if f == "all":
            return True
        if f.startswith("cat:"):
            return it.category == f[4:]
        if f == "unfinished":
            return it.status != "completed" and it.status != "seeding"
        if f == "finished":
            return it.status in ("completed", "seeding")
        if f == "queue":
            return it.in_queue
        return True

    def selected_ids(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self._visible[r] for r in rows if r < len(self._visible)]

    # ---------------------------------------------------------- toplu seçim
    SELECT_PRESETS = (("Bitmemişleri seç", lambda it: it.status not in ("completed", "seeding")),
                      ("Bitenleri seç", lambda it: it.status in ("completed", "seeding")),
                      ("Durdurulanları seç", lambda it: it.status in ("stopped", "queued")),
                      ("Hatalıları seç", lambda it: it.status == "error"))

    def _add_select_menu(self, m):
        m.addAction(self.a_select_all)
        m.addAction(self.a_select_none)
        m.addSeparator()
        for text, pred in self.SELECT_PRESETS:
            m.addAction(text, lambda p=pred: self.select_where(p))

    def select_all(self):
        self.table.selectAll()

    def select_where(self, pred):
        """Listede görünenlerden koşula uyanları seç (önceki seçim yerine)."""
        self._select_rows([r for r, iid in enumerate(self._visible) if pred(self.mgr.items[iid])])

    def _select_rows(self, rows):
        # selectRow() her çağrıda önceki seçimi siler (çoklu seçim kaybolurdu): seçim tek seferde kurulur
        from PySide6.QtCore import QItemSelection, QItemSelectionModel
        sel = QItemSelection()
        last = len(COLUMNS) - 1
        for r in rows:
            sel.select(self.table.model().index(r, 0), self.table.model().index(r, last))
        self.table.blockSignals(True)
        self.table.selectionModel().select(sel, QItemSelectionModel.ClearAndSelect)
        self.table.blockSignals(False)
        self._selection_changed()

    def _selection_changed(self):
        sel = {i.row() for i in self.table.selectedIndexes()}
        for r in range(self.table.rowCount()):
            cell = self.table.item(r, SEL)
            state = Qt.Checked if r in sel else Qt.Unchecked
            if cell and cell.checkState() != state:
                cell.setCheckState(state)
        n, total = len(sel), len(self._visible)
        head = self.table.horizontalHeaderItem(SEL)
        head.setText("☑" if total and n == total else "☐")
        self.sel_lbl.setText(f"{n} indirme seçili  " if n > 1 else "")

    def refresh(self, force=False):
        self._update_nav_counts()
        ids = [i for i in self.mgr.order if self._match(self.mgr.items[i])]
        if force or ids != self._visible:
            sel = set(self.selected_ids())
            self._visible = ids
            self.table.setRowCount(len(ids))
            for r in range(len(ids)):
                for c in range(len(COLUMNS)):
                    if not self.table.item(r, c):
                        cell = QTableWidgetItem()
                        if c == SEL:  # kutu seçimi gösterir; tıklama DownloadTable'da seçimi değiştirir
                            cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                            cell.setCheckState(Qt.Unchecked)
                        self.table.setItem(r, c, cell)
            self._select_rows([r for r, iid in enumerate(ids) if iid in sel])
        for r, iid in enumerate(self._visible):
            it = self.mgr.items[iid]
            if it.status in ("downloading", "connecting") and it.size:
                st = f"%{it.done_bytes / it.size * 100:.2f}"
                if it.status == "connecting" and it.error:
                    st = it.error
            elif it.status == "error":
                st = f"Hata: {it.error or ''}"
            else:
                st = STATUS_TEXT.get(it.status, it.status)
                if it.status in ("stopped", "queued") and it.size and it.done_bytes:
                    st += f" (%{it.done_bytes / it.size * 100:.1f})"
            if it.kind == "torrent" and it.status in ("downloading", "seeding"):
                st += f"  ·  {it.peers} eş"
            frac = (it.done_bytes / it.size if it.size and it.status in ("downloading", "connecting", "stopped",
                                                                         "queued", "error") else None)
            tone = {"completed": "ok", "seeding": "ok", "error": "bad", "downloading": "accent",
                    "converting": "accent"}.get(
                it.status, "muted" if it.status in ("stopped", "queued") else "text")
            sc = self.table.item(r, STATUS)
            if sc.data(PROGRESS_ROLE) != frac or sc.data(TONE_ROLE) != tone:
                sc.setData(PROGRESS_ROLE, frac)
                sc.setData(TONE_ROLE, tone)
            last = datetime.fromtimestamp(it.last_try).strftime("%d.%m.%Y %H:%M") if it.last_try else ""
            vals = (it.filename, fmt_size(it.size) if it.size else "", st, fmt_time(it.eta()),
                    fmt_speed(it.speed), last, it.description)
            for c, v in enumerate(vals, start=NAME):
                cell = self.table.item(r, c)
                if cell.text() != v:
                    cell.setText(v)
            cell0 = self.table.item(r, NAME)
            if cell0.data(Qt.UserRole) != it.kind + it.status:
                cell0.setData(Qt.UserRole, it.kind + it.status)
                cell0.setIcon(self._status_icon(it))

    def _status_icon(self, it):
        return theme.status_icon(it.status)

    def _update_nav_counts(self):
        """Kenar çubuğundaki her kategorinin yanında indirme sayısı."""
        items = list(self.mgr.items.values())
        saved = self._filter
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for node in [top] + [top.child(j) for j in range(top.childCount())]:
                self._filter = node.data(0, Qt.UserRole)
                n = sum(1 for it in items if self._match(it))
                if node.data(0, COUNT_ROLE) != n:
                    node.setData(0, COUNT_ROLE, n)
        self._filter = saved

    # ---------------------------------------------------------- periyodik
    def _tick(self):
        self.mgr.tick()
        while self.mgr.events:
            kind, it = self.mgr.events.pop(0)
            if kind == "completed":
                self.tray.showMessage(APP_NAME, f"İndirme tamamlandı:\n{it.filename}", self.icon, 4000)
                if it.kind == "http" and it.path.lower().endswith(".torrent") and self.mgr.torrents:
                    self.add_source(it.path)  # inen .torrent → torrent olarak indirmeyi öner
                    continue
                oc = getattr(it, "on_complete", None) or {}
                if oc.get("show_dialog", self.mgr.settings["show_complete_dialog"]):
                    self._complete_dialog(it)
                action = next((a for a in ("shutdown", "sleep", "exit") if oc.get(a)), None)
                if action:
                    bring_to_front(PowerActionDialog(self, action, oc.get("force", False),
                                                     reason=f"İndirme tamamlandı: {it.filename}"))
            elif kind == "error":
                self.tray.showMessage(APP_NAME, f"Hata: {it.filename}\n{it.error}",
                                      QSystemTrayIcon.Warning, 5000)
                self._error_dialog(it)
            elif kind == "queue_done":
                self.tray.showMessage(APP_NAME, "Kuyruktaki tüm indirmeler işlendi.", self.icon, 4000)
                action = self.mgr.settings.get("queue_done_action") or "none"
                if action in POWER_ACTIONS:
                    bring_to_front(PowerActionDialog(self, action, self.mgr.settings.get("queue_done_force", False),
                                                     reason="Kuyruktaki tüm indirmeler tamamlandı."))
            elif kind == "info":
                self.tray.showMessage(APP_NAME, it, self.icon, 3000)
        while not server.requests.empty():
            self._handle_external(server.requests.get())
        self.refresh()
        sp = self.mgr.total_speed()
        active = sum(1 for i in self.mgr.items.values() if i.status in ("downloading", "connecting"))
        q = "  ·  Kuyruk çalışıyor" if self.mgr.queue_running else ""
        self.speed_lbl.setText(f"Etkin: {active}   ·   Toplam hız: {fmt_speed(sp) or '0 B/s'}{q}")
        self.tray.setToolTip(f"{APP_NAME}\n{fmt_speed(sp) or 'Boşta'}")

    def _complete_dialog(self, it):
        path = it.path if it.kind != "torrent" else os.path.join(it.path, it.name)
        box = QMessageBox(self)
        box.setWindowTitle("İndirme tamamlandı")
        box.setIcon(QMessageBox.Information)
        box.setText(f"<b>{it.filename}</b><br>{fmt_size(it.size)}<br>{path}")
        b_open = box.addButton("Aç", QMessageBox.AcceptRole)
        b_dir = box.addButton("Klasörü Aç", QMessageBox.ActionRole)
        box.addButton("Kapat", QMessageBox.RejectRole)
        box.setAttribute(Qt.WA_DeleteOnClose)
        box.buttonClicked.connect(lambda b: open_path(path) if b is b_open
                                  else open_folder(path) if b is b_dir else None)
        bring_to_front(box)

    def perform_power_action(self, action, force=False):
        """Bitince yapılacaklar: önce indirme listesi kaydedilir, sonra işlem yapılır."""
        self.mgr.save()
        if action == "exit":
            self.quit_app()
        elif action == "shutdown":
            args = ["shutdown", "/s", "/t", "5"] + (["/f"] if force else [])
            subprocess.Popen(args, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.quit_app()
        elif action == "sleep":
            import ctypes
            ctypes.windll.powrprof.SetSuspendState(False, False, False)

    def _error_dialog(self, it):
        """İndirme hatası: IDM gibi önde bir uyarı, tek tıkla yeniden deneme."""
        box = QMessageBox(self)
        box.setWindowTitle("İndirme hatası")
        box.setIcon(QMessageBox.Warning)
        box.setText(f"<b>{it.filename}</b><br><br>{it.error or 'Bilinmeyen hata'}")
        b_retry = box.addButton("Tekrar Dene", QMessageBox.AcceptRole)
        box.addButton("Kapat", QMessageBox.RejectRole)
        box.setAttribute(Qt.WA_DeleteOnClose)
        iid = it.id
        box.buttonClicked.connect(lambda b: (self.mgr.start(iid), self.show_progress(iid)) if b is b_retry else None)
        bring_to_front(box)

    # ---------------------------------------------------------- ekleme
    def add_url_prompt(self):
        clip = QApplication.clipboard().text().strip()
        default = clip if re.match(r"^(https?|ftp)://|^magnet:", clip, re.I) else "https://"
        url, ok = QInputDialog.getText(self, "Yeni indirme", "İndirilecek adres (URL veya magnet):", text=default)
        if ok and url.strip():
            self.add_source(url.strip())

    def add_torrent_prompt(self):
        p, _ = QFileDialog.getOpenFileName(self, "Torrent dosyası seç", "", "Torrent (*.torrent)")
        if p:
            self.add_source(p)

    def add_magnet_prompt(self):
        url, ok = QInputDialog.getText(self, "Magnet ekle", "Magnet bağlantısı:")
        if ok and url.strip():
            self.add_source(url.strip())

    def add_source(self, src, headers=None, suggested=None, cookies=None):
        if is_magnet(src) or (src.lower().endswith(".torrent") and os.path.isfile(src)):
            if not self.mgr.torrents:
                QMessageBox.warning(self, APP_NAME, f"Torrent desteği yok: {self.mgr.torrent_error}")
                return
            d = TorrentAddDialog(self, src)
        elif re.match(r"^(https?|ftp)://", src, re.I):
            d = FileInfoDialog(self, src, headers, suggested, cookies)
        else:
            QMessageBox.warning(self, APP_NAME, "Geçersiz adres. http(s)://, ftp:// ya da magnet: bağlantısı girin.")
            return
        bring_to_front(d)

    def _handle_external(self, req):
        if req.get("show"):
            self.show_normal()
            return
        if req.get("quit"):
            self.quit_app()
            return
        tf = req.get("torrent_file")
        if isinstance(tf, str) and tf.lower().endswith(".torrent") and os.path.isfile(tf):
            # Tarayıcının indirdiği .torrent (site yalnızca tarayıcıya veriyorsa): dosya seçimiyle aç
            self.add_source(tf)
            return
        url = req.get("url", "")
        if isinstance(req.get("cookies"), list):  # eklentiden sayfa videosu: tek videoya indirgenir
            url = ytdlp.canonical_url(url)
        headers = {}
        if req.get("cookie"):
            headers["Cookie"] = req["cookie"]
        if req.get("referrer"):
            headers["Referer"] = req["referrer"]
        if req.get("userAgent"):
            headers["User-Agent"] = req["userAgent"]
        if isinstance(req.get("origin"), str) and re.match(r"^https?://[^/]+$", req["origin"]):
            headers["Origin"] = req["origin"]  # gömülü oynatıcının kökeni (video sunucusu denetleyebilir)
        name = os.path.basename(req.get("filename") or "") or None
        cookies = req.get("cookies") if isinstance(req.get("cookies"), list) else None
        if cookies:  # yapılandırılmış çerezler (YouTube): yt-dlp'ye çerez dosyasıyla verilir
            headers.pop("Cookie", None)
        if isinstance(req.get("choice"), dict) and req["choice"].get("format"):
            # Kalite tarayıcıdaki menüden seçildi (IDM gibi): kayıt yeri penceresi, kalite seçili gelir
            self._video_from_menu(url, req["choice"], req.get("title") or "", headers, cookies)
            return
        self.add_source(url, headers, name, cookies)

    # ---------------------------------------------------------- tarayıcıdaki kalite menüsü
    FORMAT_CACHE_SECONDS = 20 * 60

    def _formats_handler(self, data):
        """Köprü iş parçacığında çalışır (/formats): eklentinin sayfada göstereceği kalite listesi.
        Sonuç (akış adresleriyle) önbelleğe alınır; kalite seçilince YouTube'a ikinci istek gitmez."""
        url = data.get("url") or ""
        if not re.match(r"^https?://", url, re.I):
            raise ValueError("Geçersiz adres")
        url = ytdlp.canonical_url(url)
        if not ytdlp.available():
            raise RuntimeError("yt-dlp bulunamadı")
        hit = self._fmt_cache.get(url)
        if hit and time.time() - hit[0] < self.FORMAT_CACHE_SECONDS:
            info = hit[1]
        else:
            cookies = data.get("cookies") if isinstance(data.get("cookies"), list) else None
            info = ytdlp.inspect(url, self.mgr.ffmpeg(), cookies)
            self._fmt_cache[url] = (time.time(), info)
        return {"title": info["title"], "duration": info.get("duration"),
                "choices": [{k: v for k, v in c.items() if k != "streams"} for c in info["choices"]]}

    def _video_from_menu(self, url, choice, title, headers, cookies):
        """Tarayıcı menüsünde seçilen kalite: 'İndirme Dosyası Bilgisi' penceresi kalite ve uzantı seçili açılır;
        kayıt yeri / Sonra İndir / Başlat kullanıcıda. Önbellekteki bilgi kullanılır (YouTube'a yeni istek yok)."""
        hit = self._fmt_cache.get(url)
        info = hit[1] if hit and time.time() - hit[0] < self.FORMAT_CACHE_SECONDS else None
        if info is None:  # önbellek yoksa pencere kaliteleri kendisi sorgular; seçim yine uygulanır
            d = FileInfoDialog(self, url, headers, None, cookies)
            d._preselect = choice.get("format")
        else:
            d = FileInfoDialog(self, url, headers, None, cookies, video_info=info, preselect=choice.get("format"))
        bring_to_front(d)

    # ---------------------------------------------------------- güncellemeler
    def check_updates(self, prefetched=None):
        d = UpdateDialog(self, prefetched)
        bring_to_front(d)

    def _auto_update_check(self):
        """Açılıştan kısa süre sonra, günde en fazla bir kez, sessizce denetle."""
        s = self.mgr.settings
        url = updater.manifest_url(s.get("update_repo") or None)
        if not url or not s.get("auto_update_check", True) or time.time() - s.get("last_update_check", 0) < 86400:
            return
        s["last_update_check"] = time.time()
        self._upd_bridge = Bridge()
        self._upd_bridge.done.connect(self._on_auto_update)

        def work():
            try:
                self._upd_bridge.done.emit(updater.check(url), None)
            except Exception as e:  # noqa: BLE001
                self._upd_bridge.done.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_auto_update(self, info, err):
        if info and info["available"]:
            self.tray.showMessage(APP_NAME, f"Yeni sürüm var: {info['latest']}", self.icon, 5000)
            self.check_updates(prefetched=info)

    def _on_clipboard(self):
        if not self.mgr.settings["clipboard_monitor"]:
            return
        text = QApplication.clipboard().text().strip()
        if not text or text == self._last_clip or "\n" in text:
            return
        self._last_clip = text
        if is_magnet(text) and self.mgr.torrents:
            self.add_source(text)
            return
        if re.match(r"^(https?|ftp)://\S+$", text, re.I):
            path = urllib.parse.urlparse(text).path
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            if ext in CATCH_EXTS or ext in ("torrent", "m3u8"):
                if any(i.url == text for i in self.mgr.items.values()):
                    return
                self.add_source(text)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        if md.hasUrls():
            for u in md.urls():
                self.add_source(u.toLocalFile() if u.isLocalFile() else u.toString())
        elif md.hasText():
            self.add_source(md.text().strip())

    # ---------------------------------------------------------- işlemler
    def show_progress(self, iid):
        d = self.progress_dialogs.get(iid)
        if d is not None:
            try:
                bring_to_front(d)
                return
            except RuntimeError:
                pass
        d = ProgressDialog(self, iid)
        d.destroyed.connect(lambda *_: self.progress_dialogs.pop(iid, None))
        self.progress_dialogs[iid] = d
        bring_to_front(d)

    def resume_selected(self):
        for iid in self.selected_ids():
            self.mgr.start(iid)

    def stop_selected(self):
        for iid in self.selected_ids():
            self.mgr.stop(iid)

    def delete_selected(self, with_file):
        ids = self.selected_ids()
        if not ids:
            return
        if not with_file:
            box = QMessageBox(QMessageBox.Question, APP_NAME,
                              f"{len(ids)} indirme listeden silinsin mi?", parent=self)
            b_list = box.addButton("Listeden sil", QMessageBox.AcceptRole)
            b_file = box.addButton("Dosyalarla birlikte sil", QMessageBox.DestructiveRole)
            box.addButton("İptal", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is b_file:
                with_file = True
            elif box.clickedButton() is not b_list:
                return
        for iid in ids:
            self.mgr.remove(iid, with_file)
        self.refresh(force=True)

    def delete_completed(self):
        done = [i for i in self.mgr.order if self.mgr.items[i].status == "completed"]
        if done and QMessageBox.question(self, APP_NAME, f"{len(done)} tamamlanmış indirme listeden kaldırılsın mı?\n"
                                         "(Dosyalar diskte kalır.)") == QMessageBox.Yes:
            for iid in done:
                self.mgr.remove(iid, False)
            self.refresh(force=True)

    def open_options(self):
        OptionsDialog(self).exec()

    def _item_path(self, it):
        return it.path if it.kind != "torrent" else os.path.join(it.path, it.name)

    def _double_click(self, idx):
        if idx.row() >= len(self._visible):
            return
        it = self.mgr.items[self._visible[idx.row()]]
        if it.status == "completed":
            open_path(self._item_path(it))
        else:
            self.show_progress(it.id)

    def _context_menu(self, pos):
        ids = self.selected_ids()
        m = QMenu(self)
        if not ids:  # boş alana sağ tık: yalnızca toplu seçim
            self._add_select_menu(m)
            m.exec(self.table.viewport().mapToGlobal(pos))
            return
        it = self.mgr.items[ids[0]]
        many = len(ids) > 1
        if many:  # toplu işlem: hepsine uygulanan komutlar
            head = m.addAction(f"{len(ids)} indirme seçili")
            head.setEnabled(False)
            m.addSeparator()
        else:
            m.addAction("Aç", lambda: open_path(self._item_path(it))).setEnabled(it.status == "completed")
            m.addAction("Klasörü aç", lambda: open_folder(self._item_path(it)))
            m.addAction("İndirme durumu…", lambda: self.show_progress(it.id))
            m.addSeparator()
        m.addAction(self.a_resume)
        m.addAction(self.a_stop)
        m.addSeparator()
        m.addAction("Kuyruğa ekle", lambda: [self.mgr.set_queue(i, True) for i in ids])
        m.addAction("Kuyruktan çıkar", lambda: [self.mgr.set_queue(i, False) for i in ids])
        m.addSeparator()
        m.addAction("Adresleri kopyala" if many else "Adresi kopyala", lambda: QApplication.clipboard().setText(
            "\n".join(self.mgr.items[i].url for i in ids if i in self.mgr.items)))
        if not many:
            if it.kind != "torrent":
                m.addAction("İndirme adresini yenile…", lambda: self._refresh_address(it))
            else:
                m.addAction("Dosya seçimi…", lambda: self.show_progress(it.id))
        m.addSeparator()
        m.addAction(f"Sil ({len(ids)})…" if many else "Sil…", lambda: self.delete_selected(False))
        self._add_select_menu(m.addMenu("Toplu seçim"))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _refresh_address(self, it):
        """Süresi dolmuş linkler için (IDM'deki 'Refresh download address')."""
        url, ok = QInputDialog.getText(self, "Adresi yenile", "Yeni indirme adresi:", text=it.url)
        if ok and url.strip():
            self.mgr.stop(it.id)
            it.url = url.strip()
            self._last_clip = it.url
            self.mgr.save()

    # ---------------------------------------------------------- kapanış
    def closeEvent(self, e):
        if self._quitting:
            e.accept()
            return
        e.ignore()
        self.hide()
        self.tray.showMessage(APP_NAME, "Program arka planda çalışmaya devam ediyor.", self.icon, 2000)

    def quit_app(self):
        self._quitting = True
        self.timer.stop()
        for d in list(self.progress_dialogs.values()):  # bağımsız indirme pencereleri de kapansın
            d.close()
        self.mgr.shutdown()
        if self.srv:
            self.srv.shutdown()
        self.tray.hide()
        QApplication.quit()
