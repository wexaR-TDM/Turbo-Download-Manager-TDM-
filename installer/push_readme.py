"""GitHub deposunun ön sayfasını günceller: README.md + docs/ görselleri (yalnızca değişenler yüklenir).

Kaynaklar (projede):
  docs/README_GITHUB.md      → README.md
  installer/turbodm.png      → docs/logo.png
  docs/github/*.png          → docs/*.png   (ekran görüntüleri)
Kullanım: python installer/push_readme.py <kullanici/depo>   (gh ile giriş yapılmış olmalı)
"""
import base64
import glob
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def gh(*args, input_file=None):
    cmd = ["gh", "api", *args]
    if input_file:
        cmd += ["--input", input_file]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def remote_sha(repo, path):
    code, out, _ = gh(f"repos/{repo}/contents/{path}", "--jq", ".sha")
    return out if code == 0 and out else None


def git_blob_sha(data):
    import hashlib
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def put(repo, path, data, message):
    sha = remote_sha(repo, path)
    if sha == git_blob_sha(data):
        return "aynı"
    body = {"message": message, "content": base64.b64encode(data).decode()}
    if sha:
        body["sha"] = sha
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(body, f)
        code, _, err = gh("-X", "PUT", f"repos/{repo}/contents/{path}", input_file=tmp)
    finally:
        os.remove(tmp)
    if code:
        raise SystemExit(f"{path} yüklenemedi: {err}")
    return "güncellendi"


def main():
    repo = sys.argv[1]
    files = {"README.md": os.path.join(ROOT, "docs", "README_GITHUB.md"),
             "PRIVACY.md": os.path.join(ROOT, "store", "PRIVACY.md"),
             "docs/logo.png": os.path.join(ROOT, "installer", "turbodm.png")}
    for p in glob.glob(os.path.join(ROOT, "docs", "github", "*.png")):
        files["docs/" + os.path.basename(p)] = p
    for dest, src in files.items():
        with open(src, "rb") as f:
            print(f"  {dest}: {put(repo, dest, f.read(), 'README güncellendi')}")


if __name__ == "__main__":
    main()
