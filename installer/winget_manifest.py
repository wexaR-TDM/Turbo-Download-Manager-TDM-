"""winget paket bildirimi (Microsoft'un winget-pkgs deposuna gönderilecek 3 YAML dosyası).

  python installer/winget_manifest.py      → build/winget/manifests/w/wexaR-TDM/TurboDM/<sürüm>/

Kurulum dosyası dist/ klasöründen okunur (SHA-256 hesaplanır); indirme adresi GitHub sürüm sayfasıdır, bu yüzden
sürüm yayımlandıktan sonra çalıştırılır. Doğrulamak için: winget validate <klasör>
Göndermek (geliştiricinin GitHub hesabıyla, winget-pkgs'e PR): wingetcreate submit <klasör> ya da elle PR.
"""
import hashlib
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = "wexaR-TDM.TurboDM"
REPO = "wexaR-TDM/TurboDM"
MANIFEST = "1.12.0"


def main():
    with open(os.path.join(ROOT, "turbodm", "appinfo.py"), encoding="utf-8") as f:
        ver = re.search(r'VERSION = "([\d.]+)"', f.read()).group(1)
    setup = os.path.join(ROOT, "dist", f"TurboDM-Setup-{ver}.exe")
    if not os.path.isfile(setup):
        sys.exit(f"Kurulum dosyası yok: {setup} (önce build.ps1)")
    h = hashlib.sha256()
    with open(setup, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    sha = h.hexdigest().upper()
    out = os.path.join(ROOT, "build", "winget", "manifests", "w", "wexaR-TDM", "TurboDM", ver)
    os.makedirs(out, exist_ok=True)
    head = f"# yaml-language-server: $schema=https://aka.ms/winget-manifest.{{}}.{MANIFEST}.schema.json\n"
    files = {
        f"{PKG}.yaml": head.format("version") + f"""
PackageIdentifier: {PKG}
PackageVersion: {ver}
DefaultLocale: en-US
ManifestType: version
ManifestVersion: {MANIFEST}
""",
        f"{PKG}.installer.yaml": head.format("installer") + f"""
PackageIdentifier: {PKG}
PackageVersion: {ver}
InstallerType: inno
Scope: machine
ElevationRequirement: elevationRequired
UpgradeBehavior: install
Protocols:
- magnet
FileExtensions:
- torrent
Installers:
- Architecture: x64
  InstallerUrl: https://github.com/{REPO}/releases/download/v{ver}/TurboDM-Setup-{ver}.exe
  InstallerSha256: {sha}
ManifestType: installer
ManifestVersion: {MANIFEST}
""",
        f"{PKG}.locale.en-US.yaml": head.format("defaultLocale") + f"""
PackageIdentifier: {PKG}
PackageVersion: {ver}
PackageLocale: en-US
Publisher: wexaR-TDM
PublisherUrl: https://github.com/wexaR-TDM
PublisherSupportUrl: https://github.com/{REPO}/issues
PrivacyUrl: https://github.com/{REPO}/blob/main/PRIVACY.md
PackageName: TurboDM
PackageUrl: https://github.com/{REPO}
License: GPL-3.0
LicenseUrl: https://github.com/{REPO}/blob/main/LICENSE
ShortDescription: Free, open-source download manager for Windows with multi-connection downloads, a video grabber, torrent support and browser integration.
Description: |-
  TurboDM is a free, open-source (GPL v3) download manager for Windows 10/11 and an alternative to Internet Download Manager.
  It speeds up downloads with multiple connections and dynamic segmentation, resumes interrupted downloads, grabs videos (HLS/DASH) from web pages via its Edge/Chrome extension, handles magnet links and .torrent files, and includes queues, a scheduler and a speed limiter.
  No ads, no telemetry, signed updates, 7 languages.
Moniker: turbodm
Tags:
- download-manager
- downloader
- accelerator
- torrent
- video-downloader
- idm-alternative
- open-source
ReleaseNotesUrl: https://github.com/{REPO}/blob/main/RELEASE_NOTES.md
ManifestType: defaultLocale
ManifestVersion: {MANIFEST}
""",
        f"{PKG}.locale.tr-TR.yaml": head.format("locale") + f"""
PackageIdentifier: {PKG}
PackageVersion: {ver}
PackageLocale: tr-TR
ShortDescription: Windows için ücretsiz, açık kaynak indirme yöneticisi; çok bağlantılı indirme, video yakalayıcı, torrent ve tarayıcı entegrasyonu.
ReleaseNotesUrl: https://github.com/{REPO}/blob/main/SURUM_NOTLARI.md
ManifestType: locale
ManifestVersion: {MANIFEST}
""",
    }
    for name, text in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text.replace("\n\n", "\n", 1))
    print(out)


if __name__ == "__main__":
    main()
