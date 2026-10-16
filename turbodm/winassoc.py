"""Windows entegrasyonu (yalnızca geçerli kullanıcı, yönetici izni gerekmez):
  * magnet: bağlantıları ve .torrent dosyaları TurboDM ile açılsın
  * "Varsayılan uygulamalar" listesinde görünsün (RegisteredApplications)
  * Windows açılışında otomatik başlatma
"""
import ctypes
import os
import sys
import winreg
from .i18n import _t

APP = "TurboDM"
HKCU = winreg.HKEY_CURRENT_USER
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command(extra=""):
    """Paketlenmiş .exe ya da 'pythonw main.py' için komut satırı."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" {extra}'.strip()
    exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(exe):
        exe = sys.executable
    main = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{exe}" "{main}" {extra}'.strip()


def icon_path():
    return sys.executable if getattr(sys, "frozen", False) else os.path.join(
        os.path.dirname(sys.executable), "pythonw.exe")


def _set(path, name, value):
    with winreg.CreateKeyEx(HKCU, path, 0, winreg.KEY_WRITE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


def _get(path, name=""):
    try:
        with winreg.OpenKey(HKCU, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def _delete_tree(path):
    try:
        with winreg.OpenKey(HKCU, path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(path + "\\" + sub)
        winreg.DeleteKey(HKCU, path)
    except FileNotFoundError:
        pass


def _delete_value(path, name):
    try:
        with winreg.OpenKey(HKCU, path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
    except OSError:
        pass


def _notify_shell():
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    except Exception:  # noqa: BLE001
        pass


def register(root="Software"):
    """magnet: ve .torrent ilişkilendirmesi. `root` testler için değiştirilebilir."""
    classes = root + r"\Classes"
    cmd = launch_command('"%1"')
    icon = f'"{icon_path()}",0'
    # magnet: protokolü
    _set(classes + r"\magnet", "", _t("URL:Magnet bağlantısı"))
    _set(classes + r"\magnet", "URL Protocol", "")
    _set(classes + r"\magnet\DefaultIcon", "", icon)
    _set(classes + r"\magnet\shell\open\command", "", cmd)
    # ProgID'ler
    _set(classes + r"\TurboDM.magnet", "", _t("Magnet bağlantısı"))
    _set(classes + r"\TurboDM.magnet", "URL Protocol", "")
    _set(classes + r"\TurboDM.magnet\shell\open\command", "", cmd)
    _set(classes + r"\TurboDM.torrent", "", _t("Torrent dosyası"))
    _set(classes + r"\TurboDM.torrent\DefaultIcon", "", icon)
    _set(classes + r"\TurboDM.torrent\shell\open\command", "", cmd)
    # .torrent uzantısı
    _set(classes + r"\.torrent", "", "TurboDM.torrent")
    _set(classes + r"\.torrent", "Content Type", "application/x-bittorrent")
    _set(classes + r"\.torrent\OpenWithProgids", "TurboDM.torrent", "")
    # Varsayılan uygulamalar ekranı için yetenekler
    cap = root + rf"\{APP}\Capabilities"
    _set(cap, "ApplicationName", APP)
    _set(cap, "ApplicationDescription", _t("İnternet indirme yöneticisi (HTTP, FTP, HLS, BitTorrent)"))
    _set(cap + r"\URLAssociations", "magnet", "TurboDM.magnet")
    _set(cap + r"\FileAssociations", ".torrent", "TurboDM.torrent")
    _set(root + r"\RegisteredApplications", APP, cap)
    _notify_shell()


def owns_registration(root="Software"):
    """TurboDM kayıtları bu exe'ye mi ait? (Aynı bilgisayarda başka bir TurboDM kurulumu ya da geliştirme
    kopyası varsa, birini kaldırmak ötekinin kayıtlarını silmemeli.)"""
    classes = root + r"\Classes"
    mine = launch_command('"%1"')
    return mine in (_get(classes + r"\magnet\shell\open\command"),
                    _get(classes + r"\TurboDM.torrent\shell\open\command"),
                    _get(classes + r"\TurboDM.magnet\shell\open\command"))


def unregister(root="Software"):
    """Yalnızca BU exe'ye ait ilişkilendirmeleri kaldırır; başka bir kurulumunkilere dokunmaz."""
    if not owns_registration(root):
        return
    classes = root + r"\Classes"
    if (_get(classes + r"\magnet\shell\open\command") or "") == launch_command('"%1"'):
        _delete_tree(classes + r"\magnet")
    if _get(classes + r"\.torrent") == "TurboDM.torrent":
        _set(classes + r"\.torrent", "", "")
    _delete_value(classes + r"\.torrent\OpenWithProgids", "TurboDM.torrent")
    for k in ("TurboDM.magnet", "TurboDM.torrent"):
        _delete_tree(classes + "\\" + k)
    _delete_tree(root + "\\" + APP)
    _delete_value(root + r"\RegisteredApplications", APP)
    _notify_shell()


def is_registered(root="Software"):
    return _get(root + r"\Classes\magnet\shell\open\command") == launch_command('"%1"')


def user_choice_overrides():
    """Başka bir program Windows'ta 'varsayılan' olarak seçilmişse (UserChoice), Windows
    bizim kaydımızı yok sayar; bu durumda kullanıcının Ayarlar'dan seçmesi gerekir."""
    p = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\magnet\UserChoice"
    prog = _get(p, "ProgId")
    return prog if prog and prog not in ("magnet", "TurboDM.magnet") else None


def open_default_apps():
    os.startfile("ms-settings:defaultapps")


def set_autostart(enabled):
    if enabled:
        _set(RUN_KEY, APP, launch_command("--tray"))
    else:
        _delete_value(RUN_KEY, APP)


def remove_autostart_if_mine():
    """Kaldırırken: açılış kaydı yalnızca BU exe'yi gösteriyorsa silinir."""
    if _get(RUN_KEY, APP) == launch_command("--tray"):
        _delete_value(RUN_KEY, APP)


def autostart_enabled():
    return _get(RUN_KEY, APP) is not None
