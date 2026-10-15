"""TurboDM arayüz testleri (ekran dışı Qt). Yalnızca yerel sunucular; internete çıkmaz.
Çalıştırma:  python -m unittest tests.test_gui -v
"""
import atexit
import hashlib
import shutil
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ["TURBODM_LANG"] = "tr"  # testler Türkçe metinlerle yazıldı; sistem dilinden bağımsız
os.makedirs(os.path.join(ROOT, "build", "tmp"), exist_ok=True)
TMP = tempfile.mkdtemp(prefix="tdm_gui_", dir=os.path.join(ROOT, "build", "tmp"))  # proje içinde
atexit.register(shutil.rmtree, TMP, True)  # bilgisayarda test kalıntısı bırakma
atexit.register(shutil.rmtree, os.path.join(tempfile.gettempdir(), "TurboDM-update"), True)
os.environ.update(APPDATA=os.path.join(TMP, "appdata"), QT_QPA_PLATFORM="offscreen",
                  QT_QPA_FONTDIR=os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication, QTabWidget  # noqa: E402
from test_turbodm import FakeServer  # noqa: E402
from turbodm import manager as M, server, updater  # noqa: E402

APP = QApplication.instance() or QApplication([])
import turbodm.gui as G  # noqa: E402

PORT = 9690 + os.getpid() % 50
M.DEFAULT_SETTINGS.update(download_root=os.path.join(TMP, "dl"), server_port=PORT,
                          torrent_port=6990 + os.getpid() % 50, auto_update_check=False)


def pump(seconds=0.0, until=None, win=None):
    """Qt olay döngüsünü (ve TurboDM'in 0,5 sn'lik tik'ini) çalıştır."""
    end = time.time() + seconds
    while True:
        APP.processEvents()
        if until and until():
            return True
        if time.time() >= end:
            return bool(until and until())
        time.sleep(0.02)


def visible(cls_name):
    return [w for w in QApplication.topLevelWidgets() if type(w).__name__ == cls_name and w.isVisible()]


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = FakeServer()
        cls.data = os.urandom(6 * 1024 * 1024)
        cls.s.files["/arsiv.zip"] = cls.data
        cls.win = G.MainWindow(M.Manager())
        cls.win.show()
        cls.win.perform_power_action = mock.Mock()   # TESTTE GERÇEK KAPATMA/UYKU YOK

    @classmethod
    def tearDownClass(cls):
        cls.win.quit_app()
        cls.s.close()

    def close_dialogs(self):
        for w in QApplication.topLevelWidgets():
            if w is not self.win and w.isVisible():
                w.close()
        pump(0.1)

    def tearDown(self):
        self.close_dialogs()

    def test_add_download_via_dialog_and_progress_window(self):
        d = G.FileInfoDialog(self.win, self.s.url("/arsiv.zip"))
        d.show()
        self.assertTrue(pump(10, lambda: "Devam ettirme" in d.size_lbl.text()), d.size_lbl.text())
        self.assertEqual(d.cat.currentData(), "compressed")
        self.assertTrue(d.path_edit.text().endswith("Compressed"), "alan yalnızca klasör olmalı")
        d._go(True)
        it = [i for i in self.win.mgr.items.values() if i.url.endswith("arsiv.zip")][-1]
        pd = self.win.progress_dialogs.get(it.id)
        self.assertIsNotNone(pd, "ilerleme penceresi açılmadı")
        # ana pencereye bağlı değil: ana pencere simge durumuna küçültülünce indirme penceresi açık kalır
        self.assertIsNone(pd.parentWidget())
        self.win.showMinimized()
        pump(0.2)
        self.assertTrue(pd.isVisible() and not pd.isMinimized())
        self.win.showNormal()
        for hint in (G.Qt.WindowMinimizeButtonHint, G.Qt.WindowMaximizeButtonHint, G.Qt.WindowCloseButtonHint):
            self.assertTrue(pd.windowFlags() & hint, f"başlık çubuğunda düğme yok: {hint}")
        tabs = pd.findChild(QTabWidget)
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],
                         ["İndirme durumu", "Hız sınırlayıcı", "Bitince yapılacaklar"])
        self.assertTrue(pump(30, lambda: it.status == "completed"), it.error)
        self.assertEqual(open(it.path, "rb").read(), self.data)
        self.assertTrue(visible("QMessageBox"), "'İndirme tamamlandı' penceresi açılmadı")

    def test_complete_action_countdown_can_be_cancelled(self):
        self.s.files["/b.bin"] = os.urandom(2 * 1024 * 1024)
        it = self.win.mgr.add_http(self.s.url("/b.bin"), os.path.join(TMP, "dl", "b.bin"), start=False)
        it.on_complete = {"show_dialog": False, "shutdown": True}
        self.win.mgr.start(it.id)
        self.assertTrue(pump(30, lambda: visible("PowerActionDialog")), "geri sayım açılmadı")
        dlg = visible("PowerActionDialog")[0]
        self.assertIn("kapatılacak", dlg.msg.text())
        dlg.reject()
        pump(1.5)
        self.win.perform_power_action.assert_not_called()

    def test_error_dialog_has_retry(self):
        it = self.win.mgr.add_http(self.s.url("/yok.bin"), os.path.join(TMP, "dl", "yok.bin"), start=True)
        self.assertTrue(pump(20, lambda: it.status == "error"))
        pump(1)
        boxes = [b for b in visible("QMessageBox") if b.windowTitle() == "İndirme hatası"]
        self.assertTrue(boxes, "hata penceresi açılmadı")
        self.assertIn("Tekrar Dene", [b.text() for b in boxes[0].buttons()])

    def test_dialogs_open(self):
        for cls in (G.OptionsDialog, G.SchedulerDialog):
            d = cls(self.win)
            d.show()
            pump(0.2)
            d.close()
        tabs = G.OptionsDialog(self.win).findChild(QTabWidget)
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())], ["Genel", "Bağlantı", "Video", "Torrent"])

    def test_update_check_download_verify_and_reject_corrupt(self):
        setup = os.urandom(500_000)
        manifest = {"version": "99.0.0", "build": "x", "url": self.s.url("/TurboDM-Setup-99.exe"),
                    "sha256": hashlib.sha256(setup).hexdigest(), "size": len(setup), "notes": "• deneme"}
        from test_turbodm import sign_manifest  # test anahtarıyla imzalı güncelleme bilgisi
        pub = sign_manifest(manifest)
        self.s.files["/latest.json"] = json.dumps(manifest).encode()
        self.s.files["/TurboDM-Setup-99.exe"] = setup
        launched = []
        with mock.patch.object(self.win.mgr, "settings", dict(self.win.mgr.settings, update_repo=self.s.url("/latest.json"))), \
                mock.patch.object(updater, "PUBLIC_KEYS", (pub,)), \
                mock.patch.object(updater, "ALLOWED_DOWNLOAD", (self.s.url("/"),)), \
                mock.patch.object(updater, "run_installer", launched.append), \
                mock.patch.object(G.ytdlp, "update_available", return_value=("1", "1", False)):
            d = G.UpdateDialog(self.win)
            d.show()
            self.assertTrue(pump(10, lambda: d.app_btn.isVisible()), d.app_lbl.text())
            self.assertTrue(d.app_note.isVisible() and "kaldığı yerden" in d.app_note.text())
            d._install()
            self.assertTrue(pump(15, lambda: launched), d.app_lbl.text())
            self.assertEqual(open(launched[0], "rb").read(), setup)
            d.close()
            # bozuk dosya: kurulum başlatılmamalı
            self.s.files["/TurboDM-Setup-99.exe"] = setup[:-1] + b"\0"
            launched.clear()
            d = G.UpdateDialog(self.win)
            d.show()
            pump(10, lambda: d.app_btn.isVisible())
            d._install()
            self.assertTrue(pump(15, lambda: "başarısız" in d.app_lbl.text()), d.app_lbl.text())
            self.assertEqual(launched, [])

    def test_browser_menu_flow_opens_preselected_dialog(self):
        info = {"title": "Deneme | Video ™", "duration": 10, "extractor": "Youtube", "choices": [
            {"label": "720p", "format": "22", "ext": "mp4", "size": 1000, "height": 720, "streams": None},
            {"label": "Yalnızca ses · m4a", "format": "140", "ext": "m4a", "size": 100, "height": 0, "streams": None}]}
        with mock.patch.object(G.ytdlp, "inspect", return_value=info):
            url = "https://www.youtube.com/watch?v=MENU"
            body = json.dumps({"url": url, "cookies": []}).encode()
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}/formats", data=body,
                                         headers={"X-TurboDM": "1", "Content-Type": "application/json"})
            res = {}
            threading.Thread(target=lambda: res.update(json.load(urllib.request.urlopen(req, timeout=10))),
                             daemon=True).start()
            self.assertTrue(pump(10, lambda: res))
            self.assertEqual([c["label"] for c in res["choices"]], ["720p", "Yalnızca ses · m4a"])
            server.requests.put({"url": url, "title": res["title"], "choice": res["choices"][1], "cookies": []})
            self.assertTrue(pump(5, lambda: visible("FileInfoDialog")))
            d = visible("FileInfoDialog")[0]
            self.assertEqual(d.quality.currentText(), "Yalnızca ses · m4a")
            self.assertEqual(d.name, "Deneme _ Video ™.m4a")
            self.assertFalse(any(i.url == url for i in self.win.mgr.items.values()), "soru sormadan başladı")

    def test_torrent_link_opens_torrent_dialog_not_html(self):
        from test_turbodm import TorrentLinkTests
        self.s.files["/x/film.torrent"] = TorrentLinkTests.TORRENT
        self.s.files["/sayfa/y.torrent"] = b"<!DOCTYPE html><html><body>Download</body></html>"
        # site torrent yerine indirme sayfası veriyor: .html kaydedilmemeli, ne yapılacağı anlatılmalı
        d = G.FileInfoDialog(self.win, self.s.url("/sayfa/y.torrent"))
        d.show()
        self.assertTrue(pump(10, lambda: "web sayfası" in d.size_lbl.text()), d.size_lbl.text())
        self.assertFalse(any(b.isEnabled() for b in d.go_buttons))
        d.close()
        if not self.win.mgr.torrents:
            self.skipTest("libtorrent yok")
        # gerçek .torrent bağlantısı: doğrudan torrent dosya seçimi penceresi
        d = G.FileInfoDialog(self.win, self.s.url("/x/film.torrent"))
        d.show()
        self.assertTrue(pump(10, lambda: visible("TorrentAddDialog")), d.size_lbl.text())
        self.assertFalse(d.isVisible())
        self.close_dialogs()
        # tarayıcının indirdiği .torrent (eklenti köprüsü)
        p = os.path.join(TMP, "tarayici.torrent")
        with open(p, "wb") as f:
            f.write(TorrentLinkTests.TORRENT)
        server.requests.put({"url": "https://site/x.torrent", "torrent_file": p})
        self.assertTrue(pump(5, lambda: visible("TorrentAddDialog")))
        self.assertFalse(visible("FileInfoDialog"), "torrent dosyası HTTP indirmesi olarak açılmamalı")

    def test_bulk_selection_with_checkboxes(self):
        from PySide6.QtCore import Qt as QtC
        from PySide6.QtTest import QTest
        win, t = self.win, self.win.table
        for iid in list(win.mgr.order):  # önceki testlerin kayıtları
            win.mgr.remove(iid, False)
        d = os.path.join(TMP, "toplu")
        items = [win.mgr.add_http(self.s.url(f"/t{i}.bin"), os.path.join(d, f"t{i}.bin"), start=False)
                 for i in range(4)]
        items[3].status = "completed"
        win.refresh(force=True)
        pump(0.2)

        def click_box(row):
            rect = t.visualRect(t.model().index(row, G.SEL))
            QTest.mouseClick(t.viewport(), QtC.LeftButton, QtC.NoModifier, rect.center())
            pump(0.05)

        click_box(0)
        click_box(2)  # Ctrl'siz: önceki seçim korunmalı
        self.assertEqual(win.selected_ids(), [items[0].id, items[2].id])
        self.assertEqual([t.item(r, G.SEL).checkState() == QtC.Checked for r in range(4)], [True, False, True, False])
        self.assertIn("2 indirme seçili", win.sel_lbl.text())
        click_box(0)  # tekrar tıklayınca seçimden çıkar
        self.assertEqual(win.selected_ids(), [items[2].id])
        t.horizontalHeader().sectionClicked.emit(G.SEL)  # başlık kutusu: tümü
        self.assertEqual(len(win.selected_ids()), 4)
        self.assertEqual(t.horizontalHeaderItem(G.SEL).text(), "☑")
        t.horizontalHeader().sectionClicked.emit(G.SEL)  # tekrar: hiçbiri
        self.assertEqual(win.selected_ids(), [])
        win.select_where(win.SELECT_PRESETS[0][1])  # bitmemişler
        self.assertEqual(win.selected_ids(), [i.id for i in items[:3]])
        win.refresh(force=True)  # liste yenilenince çoklu seçim korunmalı
        self.assertEqual(win.selected_ids(), [i.id for i in items[:3]])
        with mock.patch.object(G.QMessageBox, "exec", lambda self: None), \
                mock.patch.object(G.QMessageBox, "clickedButton",
                                  lambda self: next(b for b in self.buttons() if b.text() == "Listeden sil")):
            win.delete_selected(False)  # toplu silme
        self.assertEqual(win.mgr.order, [items[3].id])

    def test_theme_light_dark_switch(self):
        from PySide6.QtGui import QPalette
        try:
            for mode, dark in (("light", False), ("dark", True)):
                G.theme.apply(APP, mode)
                pump(0.1)
                self.assertEqual(G.theme.T["dark"], dark)
                bg = APP.palette().color(QPalette.Window)
                self.assertEqual(bg.lightness() < 128, dark, mode)
                self.assertIn(G.theme.T["accent"].lower(), APP.styleSheet().lower())
                # simgeler yeniden çizildi (araç çubuğu eylemleri)
                self.assertFalse(self.win.a_add.icon().isNull())
            self.assertIsNotNone(G.theme.status_icon("completed"))
        finally:
            G.theme.apply(APP, "auto")

    def test_new_windows_open_centered(self):
        from PySide6.QtGui import QCursor, QGuiApplication
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "orta.zip"), start=False)
        for d in (G.OptionsDialog(self.win), G.ProgressDialog(self.win, it.id)):
            d.show()
            pump(0.2)
            c = d.frameGeometry().center()
            self.assertLess(abs(c.x() - g.center().x()), 40, type(d).__name__)
            self.assertLess(abs(c.y() - g.center().y()), 60, type(d).__name__)
            d.close()
        self.win.mgr.remove(it.id, False)

    def test_dash_stream_opens_video_dialog_with_format_choice(self):
        info = {"title": "Örnek akış", "duration": 60, "extractor": "Generic", "choices": [
            {"label": "1080p · mp4", "format": "v1080+a", "ext": "mp4", "size": 1000, "height": 1080, "streams": None}]}
        seen = {}

        def fake_inspect(url, ffmpeg=None, cookies=None, headers=None):
            seen.update(url=url, headers=headers)
            return info
        with mock.patch.object(G.ytdlp, "inspect", fake_inspect), mock.patch.object(G.ytdlp, "available", lambda: True):
            hdr = {"Referer": "https://oynatici.example/embed/1", "Origin": "https://oynatici.example"}
            d = G.FileInfoDialog(self.win, "https://cdn.example/akis/manifest.mpd", hdr)
            d.show()
            self.assertTrue(pump(10, lambda: d.video_info), d.size_lbl.text())
            self.assertEqual(seen["url"], "https://cdn.example/akis/manifest.mpd")
            self.assertEqual(seen["headers"]["Origin"], "https://oynatici.example")  # oynatıcının kökeni iletilir
            self.assertTrue(d.form.isRowVisible(d.fmt), "biçim seçimi görünmüyor")
            self.assertEqual([d.fmt.itemData(i) for i in range(d.fmt.count())], ["", "mkv", "avi", "mp3"])
            # seçilen biçim indirmeye yazılır (indirme bitince dönüştürülür)
            d.fmt.setCurrentIndex(d.fmt.findData("mkv"))
            before = set(self.win.mgr.items)
            d._go(False)
            new = [self.win.mgr.items[i] for i in self.win.mgr.items if i not in before]
            self.assertEqual(len(new), 1)
            self.assertEqual(new[0].extra.get("convert"), "mkv")
            self.win.mgr.remove(new[0].id, False)

    def test_release_notes_menu_opens_public_notes(self):
        opened = []
        with mock.patch.object(G.QDesktopServices, "openUrl", lambda u: opened.append(u.toString())):
            act = next(a for m in self.win.menuBar().findChildren(G.QMenu) for a in m.actions()
                       if a.text() == "Sürüm notları")
            act.trigger()
        self.assertEqual(opened, ["https://github.com/wexaR-TDM/TurboDM/blob/main/SURUM_NOTLARI.md"])

    def test_smooth_progress_is_fluid_monotonic_and_honest(self):
        # gerçek değer yarım saniyede bir 50 MB'lık sıçramalarla gelir (video indirme gibi);
        # ekranda saniyede ~30 kare: sıçramadan, geri gitmeden, gerçeğin fazla önüne geçmeden ilerlemeli
        s = G.SmoothProgress()
        size, speed = 2_000_000_000, 100e6
        t, actual, prev, steps = 0.0, 0, None, []
        while t < 10:
            if int(t * 1000) % 500 < 33:
                actual = min(size, actual + 50_000_000)
            shown, _ = s.step(actual, speed, size, True, now=t)
            if prev is not None:
                self.assertGreaterEqual(shown, prev)  # geri gitmez
                steps.append(shown - prev)
            self.assertLessEqual(shown, actual + speed * s.LOOKAHEAD + 1)  # gerçeğin en fazla ~1 sn önünde
            prev = shown
            t += 0.033
        self.assertLess(max(steps) / size, 0.005)  # kare başına %0.5'ten az (eskiden %2.5'lik sıçrama)
        # duraklatınca/bitince gösterilen değer gerçek değere hemen eşitlenir, hız 0
        self.assertEqual(s.step(actual, 0, size, False, now=t), (actual, 0.0))
        # bağlantı satırları: hız verilmez, artıştan tahmin edilir; yine akıcı ve geri gitmeyen
        c = G.SmoothProgress()
        t, actual, prev, moved = 0.0, 0, None, 0
        while t < 5:
            if int(t * 1000) % 500 < 33:
                actual += 5_000_000  # bağlantı başına ~10 MB/s, yarım saniyede bir
            shown, _ = c.step(actual, None, 700_000_000, True, now=t)
            if prev is not None:
                self.assertGreaterEqual(shown, prev)
                moved += shown != prev
            prev = shown
            t += 0.033
        self.assertGreater(moved, 100)  # 150 karenin çoğunda ilerledi (yarım saniyede bir sıçrama değil)

    def test_progress_values_redraw_fast(self):
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "akici.zip"), start=False)
        try:
            d = G.ProgressDialog(self.win, it.id)
            self.assertLessEqual(d.anim.interval(), 50)  # indirme penceresi: ~30 kare/sn
            self.assertLessEqual(self.win.anim.interval(), 50)  # ana liste: ~20 kare/sn
            d.close()
        finally:
            self.win.mgr.remove(it.id, False)

    def test_tray_hint_shown_only_once(self):
        # pencere kapatılınca tepsiye iner; "arka planda çalışıyor" bildirimi yalnızca ilk sefer
        shown = []
        self.win.mgr.settings.pop("tray_hint_shown", None)
        with mock.patch.object(self.win.tray, "showMessage", lambda *a, **k: shown.append(a)):
            for _ in range(3):
                self.win.show()
                self.win.close()
                APP.processEvents()
        self.assertEqual(len(shown), 1)
        self.assertTrue(self.win.mgr.settings["tray_hint_shown"])

    def test_language_menu_switches_instantly(self):
        # menü çubuğunda sabit "Language" menüsü; seçince program kapanmadan her şey yeni dilde
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "dil.zip"), start=False)
        self.win.refresh(force=True)
        self.win.show_progress(it.id)
        try:
            titles = lambda: [a.text() for a in self.win.menuBar().actions()]  # noqa: E731
            self.assertEqual(titles()[-1], "&Language")
            lang_menu = self.win.menuBar().findChild(G.QMenu, "language")
            de = next(a for a in lang_menu.actions() if a.data() == "de")
            de.trigger()
            APP.processEvents()
            self.assertIn("&Hilfe", titles())
            self.assertEqual(titles()[-1], "&Language")
            self.assertEqual(self.win.table.horizontalHeaderItem(G.NAME).text(), "Dateiname")
            self.assertEqual(self.win.mgr.settings["language"], "de")
            row = self.win._visible.index(it.id)
            self.assertEqual(self.win.table.item(row, G.STATUS).text(), G.STATUS_TEXT[it.status])
            self.assertNotEqual(G.STATUS_TEXT["queued"], "Kuyrukta")
            self.assertIn(it.id, self.win.progress_dialogs)  # açık indirme penceresi yeniden açıldı
            first = self.win.menuBar().findChild(G.QMenu, "language").actions()[0]
            self.assertEqual(first.data(), "auto")  # ilk seçenek: sistem dili (varsayılan)
            self.assertFalse(first.isChecked())
            self.win.set_language("auto")
            self.assertEqual(G.i18n.language(), G.i18n.system_language())
            self.assertEqual(self.win.mgr.settings["language"], "auto")
            self.win.set_language("ar")
            self.assertEqual(APP.layoutDirection(), G.Qt.RightToLeft)
        finally:
            self.win.set_language("tr")
            APP.processEvents()
            self.assertEqual(APP.layoutDirection(), G.Qt.LeftToRight)
            self.assertIn("&Yardım", [a.text() for a in self.win.menuBar().actions()])
            for d in list(self.win.progress_dialogs.values()):
                d.close()
            self.win.mgr.remove(it.id, False)

    def test_list_survives_restart(self):
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "kalici.zip"), start=False)
        self.win.mgr.save()
        m2 = M.Manager()
        try:
            self.assertIn(it.id, m2.items)
            self.assertEqual(m2.items[it.id].status, "queued")
        finally:
            if m2.torrents:
                m2.torrents.shutdown()


try:
    import libtorrent as lt
except ImportError:
    lt = None


@unittest.skipUnless(lt, "libtorrent yok")
class TorrentGuiTests(unittest.TestCase):
    def test_magnet_metadata_file_selection_download(self):
        seeddir = os.path.join(TMP, "seed")
        album = os.path.join(seeddir, "Album")
        os.makedirs(os.path.join(album, "CD2"), exist_ok=True)
        files = {"01.flac": os.urandom(1_500_000), "02.flac": os.urandom(1_000_000),
                 os.path.join("CD2", "big.iso"): os.urandom(2_000_000)}
        for n, d in files.items():
            open(os.path.join(album, n), "wb").write(d)
        fs = lt.file_storage()
        lt.add_files(fs, album)
        ct = lt.create_torrent(fs, 256 * 1024)
        lt.set_piece_hashes(ct, seeddir)
        ti = lt.torrent_info(lt.bencode(ct.generate()))
        port = 7100 + os.getpid() % 50
        seeder = lt.session({"listen_interfaces": f"127.0.0.1:{port}", "enable_dht": False, "enable_lsd": False,
                             "enable_upnp": False, "enable_natpmp": False,
                             "allow_multiple_connections_per_ip": True})
        p = lt.add_torrent_params()
        p.ti, p.save_path = ti, seeddir
        seeder.add_torrent(p)
        win = G.MainWindow(M.Manager())   # kendi penceresi: önceki sınıf kendi penceresini kapatmış olabilir
        win.perform_power_action = mock.Mock()
        self.addCleanup(win.quit_app)
        mgr = win.mgr
        d = G.TorrentAddDialog(win, lt.make_magnet_uri(ti) + f"&x.pe=127.0.0.1:{port}")
        d.show()
        self.assertTrue(pump(30, lambda: d.ti is not None), "meta veri gelmedi")
        names = [leaf.text(0) for leaf, _ in d.files.leaves]
        self.assertEqual(sorted(names), ["01.flac", "02.flac", "big.iso"], "dolgu dosyaları gizlenmeli")
        for leaf, _ in d.files.leaves:
            if leaf.text(0) == "02.flac":
                from PySide6.QtCore import Qt
                leaf.setCheckState(0, Qt.Unchecked)
        d._go(True)
        it = [i for i in mgr.items.values() if i.kind == "torrent"][-1]
        self.assertTrue(pump(60, lambda: it.status == "completed"), it.error)
        base = os.path.join(it.path, "Album")
        self.assertEqual(open(os.path.join(base, "01.flac"), "rb").read(), files["01.flac"])
        self.assertEqual(open(os.path.join(base, "CD2", "big.iso"), "rb").read(), files[os.path.join("CD2", "big.iso")])
        f2 = os.path.join(base, "02.flac")
        self.assertFalse(os.path.exists(f2) and open(f2, "rb").read() == files["02.flac"], "seçilmeyen dosya indi")
        seeder.pause()


if __name__ == "__main__":
    unittest.main(verbosity=2)
