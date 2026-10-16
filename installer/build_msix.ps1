# Microsoft Store (MSIX) paketi: build.ps1'in hazırladığı program klasöründen dist\TurboDM-<sürüm>.msix üretir.
# Kullanım: powershell -ExecutionPolicy Bypass -File installer\build_msix.ps1 [-Stage <klasör>] [-Register]
#   -Register : paketi bu bilgisayarda dener (Windows "Geliştirici Modu" açık olmalı; Store kimliği gerekmez)
# Paket imzasızdır: Store'a yüklenince Microsoft imzalar. Kimlik bilgileri installer\msix\identity.json'da.
param([string]$Stage, [switch]$Register)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
if (-not $Stage) {
    $Stage = Join-Path $root "build\stage\TurboDM"
    if ($Stage.Length -gt 90) { $Stage = Join-Path $env:LOCALAPPDATA "TurboDM-build\stage\TurboDM" }
}
if (-not (Test-Path (Join-Path $Stage "TurboDM.exe"))) { throw "Program klasörü yok: $Stage (önce build.ps1 -NoInstall)" }
$tools = Join-Path $root "vendor\msix"
if (-not (Test-Path "$tools\makeappx.exe")) { throw "vendor\msix\makeappx.exe yok (installer\fetch_tools.ps1)" }

$appinfo = Get-Content (Join-Path $root "turbodm\appinfo.py") -Raw -Encoding UTF8
$version = [regex]::Match($appinfo, 'VERSION\s*=\s*"([^"]+)"').Groups[1].Value
$parts = ($version.Split(".") + @("0", "0", "0"))[0..2]
$msixVersion = ($parts -join ".") + ".0"   # Store: dört parçalı, sonuncusu 0 olmalı
$id = Get-Content (Join-Path $PSScriptRoot "msix\identity.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ($id.dev) { Write-Warning "identity.json geliştirme kimliğinde (dev=true): paket yalnızca bu bilgisayarda denemek içindir, Store'a gönderilmez." }

Write-Host "TurboDM $version → MSIX $msixVersion ($($id.IdentityName))"
$work = Join-Path $root "build\msix"
$pkg = Join-Path $work "pkg"
Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $pkg | Out-Null

# Program dosyaları. Store sürümünde tarayıcı eklentisi Edge mağazasından kurulur: eklenti klasörü ve
# "Program Files" yolunu anlatan kurulum yardımı pakete girmez.
Copy-Item (Join-Path $Stage "*") $pkg -Recurse
foreach ($skip in "browser_extension", "TARAYICI_EKLENTISI.txt", "BROWSER_EXTENSION.txt") {
    Remove-Item -LiteralPath (Join-Path $pkg $skip) -Recurse -Force -ErrorAction SilentlyContinue
}

# Görseller
python (Join-Path $PSScriptRoot "make_icon.py") --msix (Join-Path $pkg "Assets") | Out-Null
if ($LASTEXITCODE) { throw "Store görselleri üretilemedi" }

# Bildirim (AppxManifest.xml)
$xml = Get-Content (Join-Path $PSScriptRoot "msix\AppxManifest.xml") -Raw -Encoding UTF8
$esc = { param($s) [Security.SecurityElement]::Escape($s) }
$xml = $xml.Replace("{{IdentityName}}", (& $esc $id.IdentityName)).Replace("{{Publisher}}", (& $esc $id.Publisher)).
            Replace("{{PublisherDisplayName}}", (& $esc $id.PublisherDisplayName)).Replace("{{Version}}", $msixVersion)
if ($xml -match "\{\{") { throw "AppxManifest.xml içinde doldurulmamış alan kaldı" }
[IO.File]::WriteAllText((Join-Path $pkg "AppxManifest.xml"), $xml, (New-Object Text.UTF8Encoding $false))

# Kaynak dizini (resources.pri): ölçeğe göre görsel seçimi için
Push-Location $work
try {
    & "$tools\makepri.exe" createconfig /cf priconfig.xml /dq en-US /o | Out-Null
    if ($LASTEXITCODE) { throw "makepri createconfig başarısız" }
    & "$tools\makepri.exe" new /pr $pkg /cf priconfig.xml /mn (Join-Path $pkg "AppxManifest.xml") /of (Join-Path $pkg "resources.pri") /o | Out-Null
    if ($LASTEXITCODE) { throw "makepri new başarısız" }
} finally { Pop-Location }

if ($Register) {
    # Geliştirici Modu ile paketi kurmadan, klasörden kaydet (yalnızca deneme)
    Get-AppxPackage -Name $id.IdentityName | Remove-AppxPackage -ErrorAction SilentlyContinue
    Add-AppxPackage -Register (Join-Path $pkg "AppxManifest.xml")
    Write-Host "Bu bilgisayara kaydedildi: Başlat menüsünde 'TurboDM' (Store sürümü). Kaldırmak için: Get-AppxPackage $($id.IdentityName) | Remove-AppxPackage"
    return
}

$out = Join-Path $root "dist\TurboDM-$version.msix"
New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
& "$tools\makeappx.exe" pack /d $pkg /p $out /o | Out-Null
if ($LASTEXITCODE) { throw "makeappx pack başarısız (bildirim ya da dosyalar Store kurallarına uymuyor)" }
Write-Host ("Hazır: {0}  ({1:N1} MB)" -f $out, ((Get-Item $out).Length / 1MB))
