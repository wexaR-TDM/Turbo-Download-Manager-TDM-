"""Çok dil desteği.

Kaynak dil Türkçedir: kodda metinler Türkçe yazılır ve _t() ile sarılır, diğer diller
turbodm/locale/<dil>.json dosyalarından (Türkçe metin → çeviri) gelir. Çevirisi olmayan metin Türkçe kalır.

  _t("İndirme tamamlandı")               → seçili dildeki karşılığı
  _t("{0} indirme seçili").format(n)     → yer tutucular çeviride de aynen bulunur

Dil, program açılırken (bu modül ilk yüklendiğinde) ayarlardan okunur; böylece modül düzeyindeki sabitler
de doğru dilde oluşur. Dil değişikliği yeniden başlatınca uygulanır.
"""
import ctypes
import json
import os
import sys

# kod → kendi dilindeki adı (Seçenekler'deki listede böyle görünür)
LANGUAGES = {
    "tr": "Türkçe", "en": "English", "de": "Deutsch", "fr": "Français",
    "es": "Español", "ar": "العربية", "it": "Italiano",
}
RTL = {"ar"}
# Windows dil kimliğinin (LANGID) birincil kısmı → dil kodu
_WIN_PRIMARY = {0x1F: "tr", 0x09: "en", 0x07: "de", 0x0C: "fr", 0x0A: "es", 0x01: "ar", 0x10: "it"}

_lang = "tr"
_table = {}


def _locale_dir():
    base = getattr(sys, "_MEIPASS", None)  # paketlenmiş exe
    for d in ((os.path.join(base, "turbodm", "locale") if base else None),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale")):
        if d and os.path.isdir(d):
            return d
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale")


def system_language():
    """Windows'un arayüz dili desteklenenlerden biriyse o, değilse İngilizce."""
    try:
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return _WIN_PRIMARY.get(langid & 0x3FF, "en")
    except Exception:  # noqa: BLE001 (Windows dışı)
        return "en"


def resolve(setting):
    return setting if setting in LANGUAGES else system_language()


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
    if code not in LANGUAGES and code != "auto":
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
            return resolve(json.load(f).get("language", "auto"))
    except (OSError, ValueError):
        return resolve("auto")


set_language(_initial())


_qt_translator = None


def apply_to_app(app):
    """Qt'nin kendi metinleri (Tamam/İptal/Evet/Hayır, dosya pencereleri) ve sağdan sola düzen (Arapça)."""
    global _qt_translator
    from PySide6.QtCore import QLibraryInfo, Qt, QTranslator
    tr = QTranslator(app)
    if tr.load(f"qtbase_{_lang}", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)
        _qt_translator = tr
    app.setLayoutDirection(Qt.RightToLeft if is_rtl() else Qt.LeftToRight)


def restart_command():
    """Programı yeniden başlatan komut (dil değişince). --restart: eski kopya kapanana kadar bekle."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--restart"]
    main = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return [sys.executable, main, "--restart"]
