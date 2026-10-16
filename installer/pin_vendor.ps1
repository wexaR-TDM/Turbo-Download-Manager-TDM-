# Yardımcı programların (ffmpeg, yt-dlp, deno) SHA-256 özetlerini vendor\SHA256SUMS'a yazar.
# Yalnızca araçları resmi kaynaktan, doğrulayarak güncelledikten sonra çalıştırın (installer\fetch_tools.ps1).
# build.ps1 her derlemede bu listeyle karşılaştırır; uymayan dosya varsa derleme durur.
$root = Split-Path $PSScriptRoot -Parent
$files = "vendor\ffmpeg\ffmpeg.exe", "vendor\ytdlp\yt-dlp.exe", "vendor\deno\deno.exe"
$lines = foreach ($f in $files) { "{0}  {1}" -f (Get-FileHash (Join-Path $root $f) -Algorithm SHA256).Hash.ToLower(), $f }
[IO.File]::WriteAllLines((Join-Path $root "vendor\SHA256SUMS"), $lines)
$lines
