# PyInstaller tanımı — klasör (onedir) düzeni: hızlı açılış, kurulum programıyla dağıtım.
# Çalıştırma: pyinstaller installer/TurboDM.spec --distpath build/dist --workpath build/work
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))


def version_file():
    """TurboDM.exe dosya özellikleri (Ayrıntılar sekmesi): sürüm turbodm/appinfo.py'den, her derlemede."""
    import re
    with open(os.path.join(ROOT, "turbodm", "appinfo.py"), encoding="utf-8") as f:
        ver = re.search(r'VERSION = "([\d.]+)"', f.read()).group(1)
    nums = tuple(int(x) for x in (ver.split(".") + ["0"] * 4)[:4])
    dotted = ".".join(map(str, nums))
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904b0', [
      StringStruct('CompanyName', 'TurboDM'),
      StringStruct('FileDescription', 'TurboDM Download Manager'),
      StringStruct('FileVersion', '{dotted}'),
      StringStruct('InternalName', 'TurboDM'),
      StringStruct('LegalCopyright', 'GNU GPL v3'),
      StringStruct('OriginalFilename', 'TurboDM.exe'),
      StringStruct('ProductName', 'TurboDM'),
      StringStruct('ProductVersion', '{dotted}')])]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""
    path = os.path.join(workpath, "version_info.txt")  # noqa: F821 (PyInstaller tanımlar)
    os.makedirs(workpath, exist_ok=True)  # noqa: F821
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "turbodm", "locale", "*.json"), os.path.join("turbodm", "locale"))],  # çeviriler
    hiddenimports=["libtorrent", "truststore", "cryptography.hazmat.primitives.ciphers"],
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
    version=version_file(),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="TurboDM", upx=False)
