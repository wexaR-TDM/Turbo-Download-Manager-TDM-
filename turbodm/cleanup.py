"""Kaldırma temizliği: kaldırıcı (unins000.exe) program dosyalarını silmeden önce
`TurboDM.exe --cleanup ...` ile bunu çağırır.

Seçenekler:
  registry  : magnet/.torrent ilişkilendirmeleri, Windows açılışında başlatma (her zaman önerilir)
  partials  : yarım kalmış indirmeler (.tdm, .tdm_parts, bitmemiş torrent dosyaları)
  downloads : TurboDM listesindeki tamamlanmış dosyalar (yalnızca listedekiler; klasörler boş kalırsa silinir)
  appdata   : ayarlar, indirme listesi, torrent devam verileri (%APPDATA%\\TurboDM)

Güvenlik: hiçbir zaman bir klasörün tamamı körlemesine silinmez (ör. İndirilenler'in tamamı).
Yalnızca TurboDM'in kendi kayıtlarında geçen dosyalar ve sonradan boş kalan klasörler silinir.
"""
import json
import os
import shutil

from . import winassoc
from .manager import APP_DIR, CATEGORIES, DEFAULT_SETTINGS


def _load(name, default):
    for path in (os.path.join(APP_DIR, name), os.path.join(APP_DIR, name + ".bak")):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return default


def _rm(path, report):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            report.append(path)
        elif os.path.lexists(path):
            os.remove(path)
            report.append(path)
    except OSError:
        pass


def _rmdir_if_empty(path, stop_at=None):
    """Boş klasörü sil, üst klasöre doğru devam et (stop_at'e kadar)."""
    path = os.path.abspath(path)
    stop_at = os.path.abspath(stop_at) if stop_at else None
    while path and os.path.isdir(path) and path != stop_at:
        try:
            os.rmdir(path)
        except OSError:
            return
        path = os.path.dirname(path)


def _inside(path, parent):
    try:
        path, parent = os.path.abspath(path), os.path.abspath(parent)
        return os.path.commonpath([path, parent]) == parent and path != parent
    except ValueError:
        return False


def _torrent_files(it):
    """(dosya yolları, kök klasör) — .torrent kaynağından okunur."""
    src = it.get("source") or ""
    if not src.endswith(".torrent") or not os.path.isfile(src):
        return [], None
    try:
        from .torrent import file_list, lt
        ti = lt.torrent_info(src)
    except Exception:  # noqa: BLE001
        return [], None
    save = it.get("path") or ""
    paths = [os.path.join(save, p) for p, _, pad in file_list(ti) if not pad]
    paths.append(os.path.join(save, f".{ti.info_hashes().get_best()}.parts"))
    root = os.path.join(save, ti.name())
    return paths, root


def cleanup(registry=True, partials=True, downloads=False, appdata=True):
    report = []
    settings = dict(DEFAULT_SETTINGS)
    settings.update(_load("settings.json", {}))
    items = _load("downloads.json", [])
    touched_dirs = set()

    if registry:
        try:
            winassoc.unregister()
        except OSError:
            pass
        try:
            winassoc.remove_autostart_if_mine()
        except OSError:
            pass
        try:  # tarayıcıların TurboDM'i açabilmesi için yazılan kayıt (native messaging)
            from . import nativehost
            nativehost.unregister()
        except OSError:
            pass
        report.append("kayıt defteri girdileri")

    for it in items:
        done = it.get("status") == "completed"
        if it.get("kind") == "torrent":
            if (partials and not done) or (downloads and done):
                paths, root = _torrent_files(it)
                save = it.get("path") or ""
                for p in paths:
                    _rm(p, report)
                    touched_dirs.add((os.path.dirname(p), save))  # torrentin açtığı alt klasörler
                if root:
                    touched_dirs.add((root, save))
            continue
        path = it.get("path") or ""
        if not path:
            continue
        if partials:
            _rm(path + ".tdm", report)
            _rm(path + ".tdm_parts", report)
            if it.get("kind") == "ytdlp" and not done:
                from .ytdlp import partial_files
                for p in partial_files(path):
                    _rm(p, report)
        if downloads and done:
            _rm(path, report)
            if it.get("kind") == "hls":  # ffmpeg yoksa ayrı kaydedilen ses dosyası
                base = os.path.splitext(path)[0]
                for ext in (".ses.ts", ".ses.aac", ".ses.m4a", ".ses.mp3"):
                    _rm(base + ext, report)
        touched_dirs.add((os.path.dirname(path), None))

    root = settings.get("download_root") or DEFAULT_SETTINGS["download_root"]
    if downloads or partials:
        for d, stop in sorted(touched_dirs, key=lambda t: len(t[0]), reverse=True):
            if stop:  # torrent: yalnızca kayıt klasörünün altındakiler
                if _inside(d, stop):
                    _rmdir_if_empty(d, stop_at=stop)
            elif _inside(d, root):  # TurboDM klasörü dışındaki klasörlere asla dokunma
                _rmdir_if_empty(d, stop_at=root)
        for _, folder, _ in CATEGORIES.values():
            _rmdir_if_empty(os.path.join(root, folder), stop_at=root)
        # Ana klasör yalnızca TurboDM'in kendi klasörüyse (ör. İndirilenler\TurboDM) ve boşsa silinir;
        # kullanıcı ana klasörü 'İndirilenler'in kendisi yaptıysa ona dokunulmaz.
        if os.path.basename(os.path.normpath(root)).lower() == "turbodm":
            _rmdir_if_empty(root, stop_at=os.path.dirname(root))

    if appdata:
        _rm(APP_DIR, report)
        # güncellenmiş YouTube motoru (yt-dlp) ve indirilmiş güncelleme dosyaları
        local = os.environ.get("LOCALAPPDATA")
        if local:
            _rm(os.path.join(local, "TurboDM"), report)
        import tempfile
        _rm(os.path.join(tempfile.gettempdir(), "TurboDM-update"), report)
    return report
