"""Site girişi parolalarını ayarlar dosyasında açık metin tutmamak için Windows DPAPI.
Şifreli değer yalnızca aynı Windows kullanıcısı tarafından çözülebilir (başka kullanıcı ya da bilgisayar çözemez).
"""
import base64
import sys

PREFIX = "dpapi:"


def _blob(data=b""):
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf, DATA_BLOB


def _call(fn_name, data):
    import ctypes
    blob_in, _keep, DATA_BLOB = _blob(data)
    blob_out = DATA_BLOB()
    fn = getattr(ctypes.windll.crypt32, fn_name)
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError(f"{fn_name} başarısız")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def protect(text):
    """Metni şifreler; ayarlara yazılacak 'dpapi:...' değerini döndürür."""
    if not text:
        return ""
    if sys.platform != "win32":
        return "b64:" + base64.b64encode(text.encode()).decode()
    return PREFIX + base64.b64encode(_call("CryptProtectData", text.encode("utf-8"))).decode()


def unprotect(value):
    """protect() değerini çözer. Çözülemezse (başka kullanıcı/bilgisayar) boş metin."""
    if not value:
        return ""
    try:
        if value.startswith(PREFIX):
            return _call("CryptUnprotectData", base64.b64decode(value[len(PREFIX):])).decode("utf-8")
        if value.startswith("b64:"):
            return base64.b64decode(value[4:]).decode()
    except (OSError, ValueError):
        pass
    return ""
