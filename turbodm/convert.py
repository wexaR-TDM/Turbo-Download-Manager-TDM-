"""İndirme bitince biçim dönüştürme (ffmpeg): MKV, AVI, MP3.

  MKV : görüntü ve ses olduğu gibi yeni kaba aktarılır (saniyeler sürer, kayıpsız)
  AVI : eski televizyonlar/oynatıcılar için MPEG-4 (Xvid uyumlu) + MP3'e yeniden kodlanır (yavaş, hafif kayıp)
  MP3 : yalnızca ses
"""
import os
import subprocess
from .i18n import _t

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# anahtar → (kullanıcıya görünen ad, uzantı)
FORMATS = {
    "": (_t("Olduğu gibi (önerilen)"), None),
    "mkv": (_t("MKV (hızlı, kayıpsız)"), ".mkv"),
    "avi": (_t("AVI (eski TV/oynatıcılar için, yeniden kodlanır: yavaş)"), ".avi"),
    "mp3": (_t("MP3 (yalnızca ses)"), ".mp3"),
}


def target_path(src, fmt):
    """Hedef dosya: aynı ad, yeni uzantı; aynı adda dosya varsa (2), (3)… eklenir."""
    base = os.path.splitext(src)[0]
    ext = FORMATS[fmt][1]
    dst, n = base + ext, 2
    while os.path.exists(dst) and os.path.normcase(dst) != os.path.normcase(src):
        dst = f"{base} ({n}){ext}"
        n += 1
    return dst


def ffmpeg_args(ffmpeg, src, dst, fmt):
    a = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src]
    if fmt == "mkv":
        a += ["-map", "0", "-c", "copy"]
    elif fmt == "avi":
        a += ["-map", "0:v:0?", "-map", "0:a:0?", "-c:v", "mpeg4", "-vtag", "xvid", "-q:v", "3",
              "-c:a", "libmp3lame", "-q:a", "3"]
    elif fmt == "mp3":
        a += ["-vn", "-map", "0:a:0", "-c:a", "libmp3lame", "-q:a", "2"]
    else:
        raise ValueError(_t("bilinmeyen biçim: {0}").format(fmt))
    return a + [dst]


def convert(ffmpeg, src, fmt):
    """src'yi dönüştürür, başarılıysa src'yi siler ve yeni dosya yolunu döndürür; başarısızsa OSError
    (asıl dosya korunur)."""
    if not ffmpeg:
        raise OSError(_t("ffmpeg bulunamadı (Seçenekler → Video)"))
    if os.path.splitext(src)[1].lower() == FORMATS[fmt][1]:
        return src  # zaten istenen biçimde
    dst = target_path(src, fmt)
    tmp = dst + ".tdmconv" + FORMATS[fmt][1]
    r = subprocess.run(ffmpeg_args(ffmpeg, src, tmp, fmt), capture_output=True, creationflags=NO_WINDOW)
    if r.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) == 0:
        if os.path.exists(tmp):
            os.remove(tmp)
        err = (r.stderr.decode("utf-8", "replace").strip().splitlines() or [_t("bilinmeyen hata")])[-1]
        raise OSError(_t("Dönüştürülemedi: {0}").format(err))
    os.replace(tmp, dst)
    os.remove(src)
    return dst
