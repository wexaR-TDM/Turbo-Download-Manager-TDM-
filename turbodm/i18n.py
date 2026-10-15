"""Çok dil desteği.

Kaynak dil Türkçedir: kodda metinler Türkçe yazılır ve _t() ile sarılır, diğer diller
turbodm/locale/<dil>.json dosyalarından (Türkçe metin → çeviri) gelir. Çevirisi olmayan metin Türkçe kalır.

  _t("İndirme tamamlandı")               → seçili dildeki karşılığı
  _t("{0} indirme seçili").format(n)     → yer tutucular çeviride de aynen bulunur

Dil, program açılırken ayarlardan okunur (varsayılan İngilizce). Dil değişikliği anında uygulanır:
modül düzeyindeki çevrilmiş tablolar on_change() ile kaydedilir ve dil değişince yeniden doldurulur,
ana pencere menüleri/listeyi yeniden kurar (MainWindow.set_language).
"""
import json
import os
import sys

# kod → kendi dilindeki adı (Seçenekler'deki listede böyle görünür)
LANGUAGES = {
    "tr": "Türkçe", "en": "English", "de": "Deutsch", "fr": "Français",
    "es": "Español", "ar": "العربية", "it": "Italiano",
}
RTL = {"ar"}
DEFAULT = "en"

_lang = "tr"
_table = {}
_hooks = []


def _locale_dir():
    base = getattr(sys, "_MEIPASS", None)  # paketlenmiş exe
    for d in ((os.path.join(base, "turbodm", "locale") if base else None),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale")):
        if d and os.path.isdir(d):
            return d
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale")


def resolve(setting):
    """Ayardaki dil; tanımsız ya da eski "auto" değeri → İngilizce."""
    return setting if setting in LANGUAGES else DEFAULT


def set_language(code):
    global _lang, _table
    _lang = code if code in LANGUAGES else "tr"
    _table = {}
    if _lang != "tr":
        try:
            with open(os.path.join(_locale_dir(), _lang + ".json"), encoding="utf-8") as f:
                _table = json.load(f)
        except (OSError, ValueError):
            _table = {}
    for fn in list(_hooks):
        fn()


def on_change(fn):
    """Çevrilmiş metin tablosu dolduran fonksiyonu kaydeder: hemen ve her dil değişiminde çağrılır.
    Tablolar yerinde güncellenir (dict.update / list[:]), böylece 'from x import TABLO' yapanlar da yeni dili görür."""
    _hooks.append(fn)
    fn()
    return fn


def language():
    return _lang


def is_rtl():
    return _lang in RTL


def _t(text):
    """Türkçe metnin seçili dildeki karşılığı (yoksa metnin kendisi)."""
    return _table.get(text) or text


def _settings_path():
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "TurboDM", "settings.json")


def save_language_setting(code):
    """Kurulumda seçilen dili ayarlara yazar (diğer ayarlara dokunmadan). TurboDM.exe --set-language <kod>"""
    if code not in LANGUAGES:
        return False
    path = _settings_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data["language"] = code
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)
    return True


def _initial():
    """Açılışta: TURBODM_LANG ortam değişkeni (testler) > ayarlar > Windows dili."""
    env = os.environ.get("TURBODM_LANG")
    if env:
        return resolve(env)
    path = _settings_path()
    try:
        with open(path, encoding="utf-8") as f:
            return resolve(json.load(f).get("language"))
    except (OSError, ValueError):
        return DEFAULT


set_language(_initial())


_qt_translator = None


def apply_to_app(app):
    """Qt'nin kendi metinleri (Tamam/İptal/Evet/Hayır, dosya pencereleri) ve sağdan sola düzen (Arapça).
    Dil değişince yeniden çağrılır: önceki Qt çevirisi kaldırılır."""
    global _qt_translator
    from PySide6.QtCore import QLibraryInfo, Qt, QTranslator
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    tr = QTranslator(app)
    if tr.load(f"qtbase_{_lang}", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)
        _qt_translator = tr
    app.setLayoutDirection(Qt.RightToLeft if is_rtl() else Qt.LeftToRight)

