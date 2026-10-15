"""TurboDM güncelleme denetimi.

Yayın biçimi (her sürümde build.ps1 üretir, GitHub Release'e kurulum dosyasıyla birlikte yüklenir):
  latest.json = {
    "version": "1.1.0",                      # appinfo.VERSION
    "build":   "89f5ba381a86729d",           # kurulacak dosyaların parmak izi (aynı sürümün yeni derlemesi için)
    "url":     "https://github.com/<depo>/releases/download/v1.1.0/TurboDM-Setup-1.1.0.exe",
    "sha256":  "…", "size": 70000000,
    "published": "2026-10-14",
    "notes":   "• Yenilik 1\n• Düzeltme 2"
  }
Akış: latest.json okunur → sürüm/derleme karşılaştırılır → kurulum dosyası indirilir → SHA-256 doğrulanır →
kurulum dosyası çalıştırılır (TurboDM'i kendisi kapatır, güncelleme sihirbazını gösterir).
"""
import hashlib
import json
import os
import re
import tempfile
import urllib.request

from .appinfo import LEGACY_REPO, UPDATE_REPO, VERSION
from .engine import SSL_CONTEXT
from .i18n import _t

UA = {"User-Agent": f"TurboDM/{VERSION}"}

# Güncelleme imzası (Ed25519). latest.json, geliştiricinin bilgisayarındaki özel anahtarla imzalanır
# (installer/sign_update.py); program yalnızca bu açık anahtarlardan biriyle doğrulanan güncellemeyi kurar.
# Böylece GitHub hesabı ele geçirilse bile sahte bir kurulum dosyası "güncelleme" olarak dağıtılamaz.
PUBLIC_KEYS = ("OLxYNhEChWPsZ2/PgdT6lhVnGX0l9J2mK+ePGp0uZwI=",)
# İndirilmesine izin verilen tek yer: deponun resmi sürüm dosyaları
ALLOWED_DOWNLOAD = (f"https://github.com/{UPDATE_REPO}/releases/download/",
                    f"https://github.com/{LEGACY_REPO}/releases/download/")


def signed_payload(m):
    """İmzalanan içerik: 'sig' dışındaki tüm alanlar, sabit sırada (sürüm, adres, SHA-256, notlar…)."""
    body = {k: v for k, v in m.items() if k != "sig"}
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def verify_manifest(m, keys=None):
    """İmza geçerli değilse ValueError. Adres yalnızca resmi sürüm sayfası olabilir."""
    import base64
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    sig = m.get("sig")
    if not sig:
        raise ValueError(_t("Güncelleme bilgisi imzasız: güvenlik nedeniyle kurulmadı."))
    payload = signed_payload(m)
    for k in keys or PUBLIC_KEYS:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(k)).verify(base64.b64decode(sig), payload)
            break
        except (InvalidSignature, ValueError):
            continue
    else:
        raise ValueError(_t("Güncelleme imzası doğrulanamadı: dosya TurboDM geliştiricisinden gelmiyor olabilir. Güvenlik nedeniyle kurulmadı."))
    if not any(m["url"].startswith(p) for p in ALLOWED_DOWNLOAD):
        raise ValueError(_t("Güncelleme adresi resmi sürüm sayfası değil: güvenlik nedeniyle kurulmadı."))


def manifest_url(repo=None):
    repo = (repo if repo is not None else UPDATE_REPO).strip().strip("/")
    if not repo:
        return None
    if repo.startswith("http"):  # doğrudan latest.json adresi de verilebilir
        return repo
    return f"https://github.com/{repo}/releases/latest/download/latest.json"


def installed_build():
    """Kurulum programının kayıt defterine yazdığı derleme parmak izi (kurulu değilse None)."""
    try:
        import winreg
    except ImportError:
        return None
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(root, r"Software\TurboDM\Install", 0,
                                winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)) as k:
                return winreg.QueryValueEx(k, "Build")[0]
        except OSError:
            continue
    return None


def vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "0")) or (0,)


def check(url):
    """Dönüş: {"available": bool, "current", "latest", "notes", "url", "sha256", "size", "same_version"}"""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as r:
        m = json.loads(r.read().decode("utf-8-sig"))
    for k in ("version", "url", "sha256"):
        if not m.get(k):
            raise ValueError(_t("latest.json eksik alan: {0}").format(k))
    verify_manifest(m)
    cur_build = installed_build()
    newer = vkey(m["version"]) > vkey(VERSION)
    rebuilt = (vkey(m["version"]) == vkey(VERSION) and m.get("build") and cur_build
               and m["build"] != cur_build)
    return {"available": bool(newer or rebuilt), "current": VERSION, "latest": m["version"],
            "build": m.get("build"), "notes": m.get("notes", ""), "notes_en": m.get("notes_en", ""), "url": m["url"],
            "sha256": m["sha256"].lower(), "size": int(m.get("size") or 0),
            "published": m.get("published", ""), "same_version": bool(rebuilt)}


def download(info, progress=None, cancelled=None):
    """Kurulum dosyasını indirir ve SHA-256 ile doğrular; dosya yolunu döndürür.
    info, check()'ten gelir: adres ve SHA-256 imzalı güncelleme bilgisindendir."""
    if not any(info["url"].startswith(p) for p in ALLOWED_DOWNLOAD):
        raise ValueError(_t("Güncelleme adresi resmi sürüm sayfası değil: güvenlik nedeniyle indirilmedi."))
    name = os.path.basename(info["url"].split("?")[0]) or "TurboDM-Setup.exe"
    if not name.lower().endswith(".exe"):
        name += ".exe"
    folder = os.path.join(tempfile.gettempdir(), "TurboDM-update")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    h = hashlib.sha256()
    req = urllib.request.Request(info["url"], headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as r, open(path + ".part", "wb") as f:
        total = int(r.headers.get("Content-Length") or info.get("size") or 0)
        got = 0
        while True:
            if cancelled and cancelled():
                raise InterruptedError(_t("İptal edildi"))
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            if progress:
                progress(got, total)
    if h.hexdigest().lower() != info["sha256"]:
        os.remove(path + ".part")
        raise ValueError(_t("İndirilen kurulum dosyası doğrulanamadı (SHA-256 uyuşmuyor). Güncelleme yapılmadı."))
    os.replace(path + ".part", path)
    return path


def run_installer(path):
    """Kurulum dosyasını başlatır (yönetici izni ister). Kurulum, açık TurboDM'i kendisi kapatır."""
    os.startfile(path)  # noqa: S606
