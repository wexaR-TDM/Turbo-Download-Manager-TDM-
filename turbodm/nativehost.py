"""Tarayıcı eklentisi TurboDM kapalıyken onu açabilsin (native messaging).

Tarayıcı, eklentinin isteğiyle TurboDM.exe'yi "chrome-extension://<kimlik>/" bağımsız değişkeniyle çalıştırır
ve standart giriş/çıkıştan (4 bayt uzunluk + JSON) konuşur. TurboDM açık değilse program arka planda (tepside)
başlatılır, eklenti açılmasını bekleyip isteği yeniden gönderir.

Kayıt (yalnızca bu kullanıcı, yönetici izni gerekmez): %APPDATA%\\TurboDM\\native-host.json ve tarayıcıların
HKCU\\Software\\…\\NativeMessagingHosts\\com.turbodm.app anahtarı. Yalnızca TurboDM eklentisinin kimlikleri
(mağaza + bu kurulumdaki paketlenmemiş eklenti klasörü) izinlidir.
"""
import hashlib
import json
import os
import struct
import subprocess
import sys

HOST_NAME = "com.turbodm.app"
STORE_IDS = ("dpeakjonbfgodlhkbpeekljfgnpbbjai",)   # Microsoft Edge Eklentiler mağazası
BROWSER_KEYS = (r"Software\Microsoft\Edge\NativeMessagingHosts", r"Software\Google\Chrome\NativeMessagingHosts",
                r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts", r"Software\Chromium\NativeMessagingHosts")


def unpacked_id(folder):
    """Paketlenmemiş (klasörden yüklenen) eklentinin kimliği: Chromium, klasör yolunun UTF-16 SHA-256 özetinden
    üretir (sürücü harfi büyük). Ör. C:\\Program Files\\TurboDM\\browser_extension → pbnddkgjgkbobhaoagmpoeccolebabdl"""
    path = os.path.abspath(folder)
    if len(path) > 1 and path[1] == ":":
        path = path[0].upper() + path[1:]
    h = hashlib.sha256(path.encode("utf-16-le")).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in h)


def manifest_path():
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "TurboDM", "native-host.json")


def is_native_launch(args):
    return any(a.startswith("chrome-extension://") for a in args)


def register(exe=None, ext_dir=None):
    """Kaydı yazar/tazeler. Yalnızca paketlenmiş TurboDM.exe'de (geliştirme ortamında exe yok)."""
    exe = exe or (sys.executable if getattr(sys, "frozen", False) else None)
    if not exe or sys.platform != "win32":
        return False
    import winreg
    ext_dir = ext_dir or os.path.join(os.path.dirname(exe), "browser_extension")
    ids = list(STORE_IDS) + [unpacked_id(ext_dir)]
    data = {"name": HOST_NAME, "description": "TurboDM", "path": exe, "type": "stdio",
            "allowed_origins": [f"chrome-extension://{i}/" for i in ids]}
    path = manifest_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    for key in BROWSER_KEYS:
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key + "\\" + HOST_NAME, 0, winreg.KEY_WRITE) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, path)
        except OSError:
            pass
    return True


def unregister():
    """Kaldırırken: yalnızca bizim bildirim dosyamızı gösteren anahtarlar silinir."""
    if sys.platform != "win32":
        return
    import winreg
    path = manifest_path()
    for key in BROWSER_KEYS:
        sub = key + "\\" + HOST_NAME
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as k:
                mine = os.path.normcase(winreg.QueryValueEx(k, "")[0]) == os.path.normcase(path)
            if mine:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except OSError:
            pass
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------- tarayıcının çalıştırdığı taraf
def _std(which):
    """Standart giriş/çıkış dosya tanıtıcısı (penceresiz exe'de de tarayıcının verdiği boru)."""
    fd = 0 if which == "in" else 1
    try:
        os.fstat(fd)
        return fd
    except OSError:
        import ctypes
        import msvcrt
        h = ctypes.windll.kernel32.GetStdHandle(-10 if which == "in" else -11)
        return msvcrt.open_osfhandle(h, os.O_RDONLY if which == "in" else 0)


def _read_exact(fd, n):
    buf = b""
    while len(buf) < n:
        chunk = os.read(fd, n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def read_message(fd):
    head = _read_exact(fd, 4)
    if len(head) < 4:
        return None
    n = struct.unpack("<I", head)[0]
    if n > 1024 * 1024:  # eklentiden yalnızca küçük komutlar gelir
        return None
    return json.loads(_read_exact(fd, n).decode("utf-8") or "null")


def write_message(fd, obj):
    data = json.dumps(obj).encode("utf-8")
    os.write(fd, struct.pack("<I", len(data)) + data)


def launch_detached(cmd):
    """TurboDM'i tarayıcıdan bağımsız başlat: tarayıcı yardımcı programı kapatınca TurboDM açık kalmalı."""
    base = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    for flags in (base | 0x01000000, base):  # önce CREATE_BREAKAWAY_FROM_JOB (tarayıcının iş nesnesinden çık)
        try:
            subprocess.Popen(cmd, creationflags=flags, close_fds=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            continue
    return False


def run_host(is_running, launch_cmd, launch=launch_detached):
    """Tarayıcıdan gelen tek komutu yanıtlar. {"cmd": "launch"} → TurboDM kapalıysa açar."""
    fin, fout = _std("in"), _std("out")
    msg = read_message(fin)
    if not isinstance(msg, dict) or msg.get("cmd") != "launch":
        write_message(fout, {"ok": False, "error": "unknown command"})
        return 1
    if is_running():
        write_message(fout, {"ok": True, "launched": False})
        return 0
    ok = launch(launch_cmd)
    write_message(fout, {"ok": ok, "launched": ok})
    return 0 if ok else 1
