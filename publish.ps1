# Derlenmiş sürümü GitHub Releases'e yayımlar (GitHub CLI 'gh' ile).
# Önce: build.ps1. Gereksinim: https://cli.github.com  →  gh auth login
# Kullanım: powershell -ExecutionPolicy Bypass -File publish.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$appinfo = Get-Content (Join-Path $root "turbodm\appinfo.py") -Raw -Encoding UTF8
$version = [regex]::Match($appinfo, 'VERSION\s*=\s*"([^"]+)"').Groups[1].Value
$repo = [regex]::Match($appinfo, 'UPDATE_REPO\s*=\s*"([^"]*)"').Groups[1].Value
if (-not $repo) { throw "turbodm\appinfo.py içinde UPDATE_REPO boş (ör. kullanici/turbodm)" }
$setup = Join-Path $root "dist\TurboDM-Setup-$version.exe"
$latest = Join-Path $root "dist\latest.json"
foreach ($f in $setup, $latest) { if (-not (Test-Path $f)) { throw "$f yok — önce build.ps1" } }
$m = Get-Content $latest -Raw -Encoding UTF8 | ConvertFrom-Json  # UTF8 şart: yoksa Türkçe harfler bozulur
if ($m.version -ne $version) { throw "latest.json sürümü ($($m.version)) appinfo ile ($version) uyuşmuyor — build.ps1'i yeniden çalıştırın" }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) yok: https://cli.github.com" }

Write-Host "GitHub'a yayımlanacak: $repo  v$version" -ForegroundColor Cyan
# Boş depoda sürüm etiketi oluşturulamaz: ilk kez yayımlanıyorsa depoya kısa bir README eklenir
gh api "repos/$repo/commits?per_page=1" --silent 2>$null
if ($LASTEXITCODE) {
    $readme = "# TurboDM`n`nHTTP, FTP, video ve BitTorrent indirme yöneticisi.`n`n" +
              "İndirmek için: [Releases](https://github.com/$repo/releases/latest) sayfasındaki ``TurboDM-Setup-*.exe`` dosyası.`n"
    $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($readme))
    gh api -X PUT "repos/$repo/contents/README.md" -f message="TurboDM" -f content=$b64 --silent
    if ($LASTEXITCODE) { throw "Depoya README eklenemedi" }
}
# Kaynak kodu (GPL v3) ve README: sürüm etiketi bu kaydı göstersin diye sürümden önce gönderilir
$dirty = git -C $root status --porcelain
if ($dirty) { throw "Kaydedilmemiş değişiklik var: önce git commit (yayımlanan kod ile sürüm aynı olmalı)" }
git -C $root push origin main
if ($LASTEXITCODE) { throw "git push başarısız" }
$notesFile = New-TemporaryFile
# Sürüm sayfasında en üstte: hangi dosyanın indirileceği ("Source code" dosyalarını GitHub kendisi ekler)
$body = "**Kurmak için ``TurboDM-Setup-$version.exe`` dosyasını indirin** (aşağıda, Assets bölümünde).`n`n" +
        "**To install, download ``TurboDM-Setup-$version.exe``** (below, under Assets).`n`n" +
        "> ℹ️ TurboDM şu sıralar sık güncelleniyor. Güncelleme sırasında program kısa süre kapanır; kurulum bitince görev çubuğunda kendiliğinden yeniden açılır ve inmekte olan indirmeleriniz kaldığı yerden devam eder. Bir şey yapmanıza gerek yok.`n`n" + $m.notes +
        $(if ($m.notes_en) { "`n`n**English**`n`n" + $m.notes_en } else { "" }) +
        "`n`n---`n<sub>``ffmpeg-...-source.tar.gz``: kurulumla gelen ffmpeg.exe'nin birebir kaynak kodu (LGPL gereği). Kurulum için gerekmez.</sub>"
[IO.File]::WriteAllText($notesFile, $body, (New-Object Text.UTF8Encoding $false))
# LGPL: dağıtılan ffmpeg.exe'nin birebir kaynak kodu her sürümle birlikte yayımlanır
$ffsrc = Get-ChildItem (Join-Path $root "vendor\ffmpeg\source") -Filter "ffmpeg-*-source.tar.gz" | Select-Object -First 1
if (-not $ffsrc) { throw "vendor\ffmpeg\source içinde ffmpeg kaynak arşivi yok (LGPL gereği yayımlanmalı)" }
gh release create "v$version" $setup $latest $ffsrc.FullName --repo $repo --target main --title "TurboDM $version" --notes-file $notesFile --latest
if ($LASTEXITCODE) { throw "gh release create başarısız" }
Remove-Item $notesFile


# İndirme sayaçları (stats/sayac.json, yerel)
python (Join-Path $root "installer\stats.py") --kaydet
if ($LASTEXITCODE) { Write-Warning "İndirme sayaçları kaydedilemedi" }

# Eski sürümler silinmez: winget (ve başka paket yöneticileri) kayıtlı sürümün kurulum dosyasına bağlantı verir;
# onay bekleyen ya da onaylanmış bir kaydın dosyası silinirse o kayıt bozulur. GitHub'da sürüm saklamak ücretsiz.
# Güncelleme denetimi her zaman releases/latest adresini kullandığı için eski sürümler kimseyi etkilemez.
Write-Host "Yayımlandı. Kullanıcılar 'Güncellemeleri denetle' ile v$version'ı görecek:" -ForegroundColor Green
Write-Host "  https://github.com/$repo/releases/latest/download/latest.json"
