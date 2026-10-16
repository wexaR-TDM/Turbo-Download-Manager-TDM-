"""Windows güç ve etkinlik yardımcıları.
  * keep_awake(True): indirme sürerken bilgisayar uyku moduna geçmesin (ekran kapanabilir)
  * idle_seconds(): kullanıcı ne zamandır klavye/fareye dokunmuyor (hız sınırı "yalnızca kullanırken" için)
"""
import sys

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

_awake = False


def keep_awake(on):
    """Durum değişince Windows'a bildirir. Aynı iş parçacığından (arayüz zamanlayıcısı) çağrılmalıdır."""
    global _awake
    on = bool(on)
    if on == _awake or sys.platform != "win32":
        return
    try:
        import ctypes
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
        if ctypes.windll.kernel32.SetThreadExecutionState(flags):
            _awake = on
    except (AttributeError, OSError):
        pass


def is_kept_awake():
    return _awake


def idle_seconds():
    """Son klavye/fare kullanımından bu yana geçen süre (sn). Ölçülemezse 0 (kullanılıyor say)."""
    if sys.platform != "win32":
        return 0.0
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
        info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except (AttributeError, OSError):
        return 0.0
