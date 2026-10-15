# PyInstaller tanımı — klasör (onedir) düzeni: hızlı açılış, kurulum programıyla dağıtım.
# Çalıştırma: pyinstaller installer/TurboDM.spec --distpath build/dist --workpath build/work
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "turbodm", "locale", "*.json"), os.path.join("turbodm", "locale"))],  # çeviriler
    hiddenimports=["libtorrent", "cryptography.hazmat.primitives.ciphers"],
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtNetwork", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtOpenGL"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="TurboDM",
    icon=os.path.join(SPECPATH, "turbodm.ico"),
    version=os.path.join(SPECPATH, "version_info.txt"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="TurboDM", upx=False)
