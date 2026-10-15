# TurboDM derleme betiği: exe + kurulum dosyası + güncelleme bildirimi (latest.json).
# Kullanım:  powershell -ExecutionPolicy Bypass -File build.ps1
# Gereksinimler: Python 3.12 (requirements.txt + pyinstaller), Inno Setup 6,
#                vendor\ffmpeg\ffmpeg.exe, vendor\ytdlp\yt-dlp.exe, vendor\deno\deno.exe (installer\fetch_tools.ps1)
#
# Yeni sürüm yayımlama:
#   1) turbodm\appinfo.py içinde VERSION'u artırın (ör. 1.1.0 → 1.2.0)
#   2) SURUM_NOTLARI.md'nin en üstüne o sürümün bölümünü ekleyin
#   3) build.ps1  → dist\TurboDM-Setup-<sürüm>.exe ve dist\latest.json
#   4) publish.ps1 → GitHub Release (ya da iki dosyayı elle bir release'e yükleyin)
# Bu bilgisayarda TurboDM kuruluysa derlemenin sonunda otomatik olarak yeni sürüme güncellenir
# (açıksa düzgünce kapatılır, güncellenir, görev çubuğunda yeniden açılır ve inmekte olan indirmeler kaldığı yerden sürer).
# Güncellemeden yalnızca derlemek için: build.ps1 -NoInstall
param([switch]$NoInstall)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

# Sürüm ve güncelleme deposu tek yerden: turbodm\appinfo.py
$appinfo = Get-Content (Join-Path $root "turbodm\appinfo.py") -Raw -Encoding UTF8
$version = [regex]::Match($appinfo, 'VERSION\s*=\s*"([^"]+)"').Groups[1].Value
$repo = [regex]::Match($appinfo, 'UPDATE_REPO\s*=\s*"([^"]*)"').Groups[1].Value
$edgeId = [regex]::Match($appinfo, '(?m)^EDGE_EXTENSION_ID\s*=\s*"([a-p]{32})?"').Groups[1].Value
Write-Host "TurboDM $version" -ForegroundColor Cyan

foreach ($t in "vendor\ffmpeg\ffmpeg.exe", "vendor\ytdlp\yt-dlp.exe", "vendor\deno\deno.exe") {
    if (-not (Test-Path (Join-Path $root $t))) { throw "$t yok — önce: installer\fetch_tools.ps1 (ffmpeg için README)" }
}
# Kuruluma girecek yardımcı programlar, doğrulanmış hallerinden değişmiş mi? (bilgisayara bulaşan bir virüs
# bunları değiştirirse kurulum dosyasına ve oradan kullanıcılara geçmesin)
$sumsFile = Join-Path $root "vendor\SHA256SUMS"
if (-not (Test-Path $sumsFile)) { throw "vendor\SHA256SUMS yok (araçları güncelledikten sonra: installer\pin_vendor.ps1)" }
foreach ($line in Get-Content $sumsFile) {
    if ($line -match '^([0-9a-f]{64})\s+(.+)$') {
        $p = Join-Path $root $Matches[2]
        if (-not (Test-Path $p) -or (Get-FileHash $p -Algorithm SHA256).Hash.ToLower() -ne $Matches[1]) {
            throw "GÜVENLİK: $($Matches[2]) doğrulanmış halinden farklı! Derleme durduruldu."
        }
    }
}

Write-Host "1/5 Simge ve sihirbaz görselleri" -ForegroundColor Cyan
$env:QT_QPA_FONTDIR = "$env:SystemRoot\Fonts"
python installer\make_icon.py installer
if ($LASTEXITCODE) { throw "make_icon başarısız" }

Write-Host "2/5 TurboDM.exe (PyInstaller)" -ForegroundColor Cyan
python -m PyInstaller installer\TurboDM.spec --distpath build\dist --workpath build\work --noconfirm --log-level WARN
if ($LASTEXITCODE) { throw "PyInstaller başarısız" }

Write-Host "3/5 Kurulum düzeni" -ForegroundColor Cyan
# Inno Setup 260 karakterden uzun yolları okuyamaz; proje derin bir klasördeyse kısa bir yerde hazırla
$stage = Join-Path $root "build\stage\TurboDM"
if ($stage.Length -gt 90) { $stage = Join-Path $env:LOCALAPPDATA "TurboDM-build\stage\TurboDM" }
Write-Host "    $stage"
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage, (Join-Path $stage "ffmpeg"), (Join-Path $stage "tools") | Out-Null
Copy-Item (Join-Path $root "build\dist\TurboDM\*") $stage -Recurse
foreach ($f in "vendor\ffmpeg\ffmpeg.exe", "vendor\ffmpeg\LICENSE.txt", "vendor\ffmpeg\source\DERLEME_BILGISI.txt") {
    Copy-Item (Join-Path $root $f) (Join-Path $stage "ffmpeg")  # LGPL: kaynak bilgisi programla birlikte
}
Copy-Item (Join-Path $root "vendor\ytdlp\yt-dlp.exe"), (Join-Path $root "vendor\deno\deno.exe") (Join-Path $stage "tools")
Copy-Item (Join-Path $root "installer\turbodm.ico") $stage
Copy-Item (Join-Path $root "browser_extension") (Join-Path $stage "browser_extension") -Recurse
Copy-Item (Join-Path $root "installer\TARAYICI_EKLENTISI.txt") $stage
Copy-Item (Join-Path $root "installer\LISANSLAR.txt") $stage
Copy-Item (Join-Path $root "LICENSE") (Join-Path $stage "LICENSE.txt")  # GPL: lisans metni programla birlikte

# Derleme parmak izi: kurulacak tüm dosyaların içeriğinden. Aynı sürüm numarasıyla farklı bir derleme
# kurulursa kurulum programı bunu "değişiklik var" olarak algılar ve günceller.
$hashes = Get-ChildItem $stage -Recurse -File | Sort-Object FullName | ForEach-Object {
    $_.FullName.Substring($stage.Length) + ":" + (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
$sha = [Security.Cryptography.SHA256]::Create()
$build = -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($hashes -join "`n")) | Select-Object -First 8 | ForEach-Object { $_.ToString("x2") })
Write-Host "    derleme parmak izi: $build"

Write-Host "4/5 Kurulum dosyası (Inno Setup)" -ForegroundColor Cyan
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Write-Warning "Inno Setup 6 bulunamadı; kurulum dosyası atlandı (exe hazır: $stage)"; exit 0 }
& $iscc /Q "/DStage=$stage" "/DAppBuild=$build" "/DAppVersion=$version" "/DEdgeExtId=$edgeId" installer\TurboDM.iss
if ($LASTEXITCODE) { throw "Inno Setup başarısız" }
$setup = Get-Item (Join-Path $root "dist\TurboDM-Setup-$version.exe")
# dist'te yalnızca son sürümün kurulum dosyası kalsın
Get-ChildItem (Join-Path $root "dist") -Filter "TurboDM-Setup-*.exe" | Where-Object { $_.Name -ne $setup.Name } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }

Write-Host "5/5 Güncelleme bildirimi (dist\latest.json)" -ForegroundColor Cyan
$notesAll = Get-Content (Join-Path $root "SURUM_NOTLARI.md") -Raw -Encoding UTF8
$m = [regex]::Match($notesAll, '(?ms)^##\s*' + [regex]::Escape($version) + '\s*$(.*?)(?=^##\s|\z)')
$notes = if ($m.Success) { $m.Groups[1].Value.Trim() } else { "" }
if (-not $notes) { Write-Warning "SURUM_NOTLARI.md içinde '## $version' bölümü yok" }
# İndirme adresi deponun eski adıyla yazılır (GitHub yönlendirir): 1.5.7 yalnızca o adresi kabul ediyor
$legacy = [regex]::Match($appinfo, 'LEGACY_REPO\s*=\s*"([^"]*)"').Groups[1].Value
$dlRepo = if ($legacy) { $legacy } else { $repo }
$dl = if ($repo) { "https://github.com/$dlRepo/releases/download/v$version/$($setup.Name)" } else { $setup.Name }
$manifest = [ordered]@{
    version   = $version
    build     = $build
    url       = $dl
    sha256    = (Get-FileHash $setup.FullName -Algorithm SHA256).Hash.ToLower()
    size      = $setup.Length
    published = (Get-Date -Format "yyyy-MM-dd")
    notes     = $notes
}
[IO.File]::WriteAllText((Join-Path $root "dist\latest.json"), ($manifest | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
# İmza: kurulu TurboDM'ler yalnızca bu bilgisayardaki özel anahtarla imzalanmış güncellemeyi kurar
python (Join-Path $root "installer\sign_update.py") sign (Join-Path $root "dist\latest.json")
if ($LASTEXITCODE) { throw "Güncelleme bilgisi imzalanamadı (keys\update_signing.key)" }
if (-not $repo) { Write-Warning "turbodm\appinfo.py içinde UPDATE_REPO boş: latest.json'daki indirme adresi tamamlanmadı" }
Write-Host ("Hazır: {0}  ({1:N1} MB)" -f $setup.FullName, ($setup.Length / 1MB)) -ForegroundColor Green
Write-Host "Hazır: $(Join-Path $root 'dist\latest.json')" -ForegroundColor Green

$inst = Get-ItemProperty "HKLM:\Software\TurboDM\Install" -ErrorAction SilentlyContinue
if (-not $inst) { $inst = Get-ItemProperty "HKCU:\Software\TurboDM\Install" -ErrorAction SilentlyContinue }
if ($NoInstall -or -not $inst -or -not $inst.Path) { exit 0 }
Write-Host "Bu bilgisayardaki TurboDM güncelleniyor: $($inst.Version) → $version" -ForegroundColor Cyan
$exe = Join-Path $inst.Path "TurboDM.exe"
$wasRunning = [bool](Get-Process TurboDM -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe })
# kurulum programı açık TurboDM'i düzgünce kapatır (indirmelerin kaldığı yer kaydedilir)
# /relaunch=0: kurulum yönetici olarak çalıştığı için TurboDM'i burada, normal kullanıcı olarak yeniden açarız
$p = Start-Process $setup.FullName -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/relaunch=0" -Verb RunAs -PassThru -Wait
$now = Get-ItemProperty "HKLM:\Software\TurboDM\Install", "HKCU:\Software\TurboDM\Install" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $inst.Path } | Select-Object -First 1
if ($p.ExitCode -or -not $now -or $now.Build -ne $build) {
    Write-Warning "Güncelleme başarısız (çıkış kodu $($p.ExitCode)); kurulu sürüm: $($now.Version)"
} else {
    Write-Host "Kurulu TurboDM artık $version" -ForegroundColor Green
}
if ($wasRunning -and (Test-Path $exe)) {
    Start-Process $exe -ArgumentList "--minimized", "--resume"
    Write-Host "TurboDM görev çubuğunda yeniden açıldı; inmekte olan indirmeler kaldığı yerden sürüyor" -ForegroundColor Green
}
