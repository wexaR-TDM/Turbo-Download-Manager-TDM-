# Video desteği için yardımcı araçları resmi GitHub sürümlerinden indirir ve SHA-256 ile doğrular.
#   vendor\ytdlp\yt-dlp.exe   (yt-dlp, Unlicense)
#   vendor\deno\deno.exe      (deno, MIT — yt-dlp'nin YouTube şifre çözücüsü için korumalı JS motoru)
#   vendor\msix\makeappx.exe  (Microsoft, Store paketi için; NuGet: Microsoft.Windows.SDK.BuildTools)
# Kullanım: powershell -ExecutionPolicy Bypass -File installer\fetch_tools.ps1
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$root = Split-Path $PSScriptRoot -Parent
$tmp = Join-Path $env:TEMP "tdm-tools"
New-Item -ItemType Directory -Force $tmp, "$root\vendor\ytdlp", "$root\vendor\deno" | Out-Null
$h = @{ "User-Agent" = "TurboDM-build" }

# --- yt-dlp
$rel = Invoke-RestMethod "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest" -Headers $h
$exe = $rel.assets | Where-Object name -eq "yt-dlp.exe"
$sums = $rel.assets | Where-Object name -eq "SHA2-256SUMS"
Invoke-WebRequest $exe.browser_download_url -OutFile "$tmp\yt-dlp.exe" -Headers $h -UseBasicParsing
Invoke-WebRequest $sums.browser_download_url -OutFile "$tmp\sums.txt" -Headers $h -UseBasicParsing
$expected = ((Get-Content "$tmp\sums.txt") |
    Where-Object { $_ -match "\syt-dlp\.exe\s*$" }).Split(" ")[0]
$actual = (Get-FileHash "$tmp\yt-dlp.exe" -Algorithm SHA256).Hash
if ($actual -ne $expected.ToUpper()) { throw "yt-dlp.exe SHA-256 uyuşmuyor" }
Copy-Item "$tmp\yt-dlp.exe" "$root\vendor\ytdlp\yt-dlp.exe" -Force
Write-Host "yt-dlp $($rel.tag_name) doğrulandı"

# --- deno
$rel = Invoke-RestMethod "https://api.github.com/repos/denoland/deno/releases/latest" -Headers $h
$zip = $rel.assets | Where-Object name -eq "deno-x86_64-pc-windows-msvc.zip"
$sum = $rel.assets | Where-Object name -eq "deno-x86_64-pc-windows-msvc.zip.sha256sum"
Invoke-WebRequest $zip.browser_download_url -OutFile "$tmp\deno.zip" -Headers $h -UseBasicParsing
Invoke-WebRequest $sum.browser_download_url -OutFile "$tmp\deno.sha" -Headers $h -UseBasicParsing
# deno özeti ya "<hash>  <dosya>" ya da PowerShell liste biçiminde yayımlanır: 64 haneli onaltılık değeri al
$expected = [regex]::Match((Get-Content "$tmp\deno.sha" -Raw), "[0-9A-Fa-f]{64}").Value
$actual = (Get-FileHash "$tmp\deno.zip" -Algorithm SHA256).Hash
if ($actual -ne $expected.ToUpper()) { throw "deno.zip SHA-256 uyuşmuyor" }
Expand-Archive "$tmp\deno.zip" "$tmp\deno" -Force
Copy-Item "$tmp\deno\deno.exe" "$root\vendor\deno\deno.exe" -Force
Write-Host "deno $($rel.tag_name) doğrulandı"

# --- MSIX paketleme araçları (Microsoft Store sürümü için): Microsoft'un resmi NuGet paketinden yalnızca
#     MakeAppx/MakePri ve kütüphaneleri; Windows SDK kurulmaz. Her dosyanın Microsoft imzası denetlenir.
$btVer = "10.0.28000.2526"
New-Item -ItemType Directory -Force "$root\vendor\msix" | Out-Null
Invoke-WebRequest "https://api.nuget.org/v3-flatcontainer/microsoft.windows.sdk.buildtools/$btVer/microsoft.windows.sdk.buildtools.$btVer.nupkg" -OutFile "$tmp\bt.zip" -Headers $h -UseBasicParsing
Expand-Archive "$tmp\bt.zip" "$tmp\bt" -Force
foreach ($f in "makeappx.exe", "makepri.exe", "appxpackaging.dll", "appxsip.dll", "opcservices.dll", "mrmsupport.dll") {
    $src = Get-ChildItem "$tmp\bt\bin" -Recurse -Filter $f | Where-Object { $_.Directory.Name -eq "x64" } | Select-Object -First 1
    $sig = Get-AuthenticodeSignature $src.FullName
    if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notlike "CN=Microsoft Corporation*") { throw "$f Microsoft imzalı değil" }
    Copy-Item $src.FullName "$root\vendor\msix\$f" -Force
}
# MakeAppx'in yan yana (side-by-side) bileşen tanımları (imzasız metin dosyaları; özetleri SHA256SUMS'ta)
foreach ($f in "AppxPackaging", "AppxSip", "OpcServices") {
    Copy-Item "$tmp\bt\bin\*\x64\Microsoft.Windows.Build.Appx.$f.dll.manifest" "$root\vendor\msix\" -Force
}
Write-Host "MSIX araçları $btVer doğrulandı (Microsoft imzalı)"
Remove-Item -LiteralPath $tmp -Recurse -Force
