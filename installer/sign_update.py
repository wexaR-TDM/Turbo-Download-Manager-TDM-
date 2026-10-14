"""Güncelleme imzalama (Ed25519). Kurulu TurboDM'ler yalnızca bu anahtarla imzalanmış güncellemeyi kurar:
GitHub hesabı ele geçirilse bile sahte güncelleme dağıtılamaz (özel anahtar yalnızca bu bilgisayarda).

  python installer/sign_update.py keygen              → anahtar üretir (bir kez), açık anahtarı yazdırır
  python installer/sign_update.py sign dist/latest.json → latest.json'a "sig" ekler (build.ps1 çağırır)
  python installer/sign_update.py backup <dosya>      → parolalı yedek (başka bilgisayara taşımak / kaybetmemek için)
  python installer/sign_update.py restore <dosya>     → yedekten geri yükler

Özel anahtar keys/update_signing.key dosyasında Windows DPAPI ile şifreli durur: yalnızca bu Windows
kullanıcısı açabilir. Dosya kopyalansa bile başka bir bilgisayarda/kullanıcıda işe yaramaz.
"""
import base64
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KEY_FILE = os.path.join(ROOT, "keys", "update_signing.key")
sys.path.insert(0, ROOT)


# ---------------------------------------------------------------- Windows DPAPI
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _dpapi(data, protect):
    inp, _keep = _blob(data)
    out = _Blob()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(inp), None, None, None, None, 0x1, ctypes.byref(out))  # 0x1: arayüz yok
    if not ok:
        raise OSError("DPAPI işlemi başarısız (anahtar bu Windows kullanıcısına ait değil mi?)")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


# ---------------------------------------------------------------- anahtar
def _save(key):
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                            serialization.NoEncryption())
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    with open(KEY_FILE, "wb") as f:
        f.write(_dpapi(raw, True))


def load_key():
    if not os.path.isfile(KEY_FILE):
        raise SystemExit(f"İmzalama anahtarı yok: {KEY_FILE}\n(yedekten geri yükleyin: sign_update.py restore <yedek>)")
    with open(KEY_FILE, "rb") as f:
        return Ed25519PrivateKey.from_private_bytes(_dpapi(f.read(), False))


def public_b64(key):
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(pub).decode()


def keygen():
    if os.path.exists(KEY_FILE):
        raise SystemExit("Anahtar zaten var; yenisi üretilirse kurulu programlar güncelleme alamaz. İptal edildi.")
    key = Ed25519PrivateKey.generate()
    _save(key)
    print(public_b64(key))


def sign(path):
    from turbodm.updater import PUBLIC_KEYS, signed_payload
    key = load_key()
    if public_b64(key) not in PUBLIC_KEYS:
        raise SystemExit("Bu anahtarın açık anahtarı programda (updater.PUBLIC_KEYS) yok: imza işe yaramaz")
    with open(path, encoding="utf-8-sig") as f:
        m = json.load(f)
    m.pop("sig", None)
    m["sig"] = base64.b64encode(key.sign(signed_payload(m))).decode()
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    print("imzalandı:", path)


def _ask_password(confirm):
    """Parolayı küçük bir pencerede sor (yazılanlar nokta olarak görünür). Terminalde parola yazarken hiçbir
    şey görünmediği ve bazı terminallerde klavye girişi çalışmadığı için pencere kullanılır."""
    from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit)
    app = QApplication.instance() or QApplication([])  # noqa: F841
    d = QDialog()
    d.setWindowTitle("TurboDM imza anahtarı")
    f = QFormLayout(d)
    info = QLabel("Yedek için bir parola belirleyin (en az 12 karakter).\nBu parolayı unutmayın: yedeği açmak "
                  "için gerekir." if confirm else "Yedeğin parolasını girin.")
    f.addRow(info)
    p1, p2 = QLineEdit(), QLineEdit()
    for e in (p1, p2):
        e.setEchoMode(QLineEdit.Password)
        e.setMinimumWidth(280)
    f.addRow("Parola:", p1)
    if confirm:
        f.addRow("Parola (tekrar):", p2)
    err = QLabel("")
    err.setStyleSheet("color: #d93a32;")
    f.addRow(err)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    f.addRow(bb)

    def ok():
        if confirm and len(p1.text()) < 12:
            err.setText("Parola en az 12 karakter olmalı.")
        elif confirm and p1.text() != p2.text():
            err.setText("Parolalar aynı değil.")
        else:
            d.accept()
    bb.accepted.connect(ok)
    bb.rejected.connect(d.reject)
    d.raise_()
    d.activateWindow()
    if d.exec() != QDialog.Accepted:
        raise SystemExit("İptal edildi")
    return p1.text()


def backup(path):
    pw = _ask_password(confirm=True)
    pem = load_key().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.BestAvailableEncryption(pw.encode()))
    with open(path, "wb") as f:
        f.write(pem)
    print("yedek yazıldı:", path)


def restore(path):
    if os.path.exists(KEY_FILE):
        raise SystemExit("Anahtar zaten var")
    with open(path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), _ask_password(confirm=False).encode())
    _save(key)
    print("geri yüklendi; açık anahtar:", public_b64(key))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"keygen": keygen, "sign": lambda: sign(sys.argv[2]), "backup": lambda: backup(sys.argv[2]),
     "restore": lambda: restore(sys.argv[2])}.get(cmd, lambda: print(__doc__))()
