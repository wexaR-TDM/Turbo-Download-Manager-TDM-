# TurboDM test paketlerini çalıştırır. Hepsi yalnızca yerel sunucularla çalışır, internete çıkmaz.
#   powershell -ExecutionPolicy Bypass -File tests\run_tests.ps1              → motor + arayüz testleri
#   powershell -ExecutionPolicy Bypass -File tests\run_tests.ps1 -Installer   → + kurulum dosyası kur/öz-test/kaldır
# Gerekli: requirements.txt; isteğe bağlı: pyftpdlib (FTP testleri), ffmpeg (vendor\ffmpeg)
param([switch]$Installer)
$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
$failed = 0

Write-Host "== Motor, YouTube hızlı mod, HLS, FTP, yönetici, köprü, kaldırma temizliği" -ForegroundColor Cyan
python -W ignore -m unittest tests.test_turbodm
if ($LASTEXITCODE) { $failed++ }

Write-Host "== Arayüz (ekran dışı) ve torrent" -ForegroundColor Cyan
python -W ignore -m unittest tests.test_gui
if ($LASTEXITCODE) { $failed++ }

if ($Installer) {
    Write-Host "== Kurulum dosyası: kur → öz-test → kaldır (yönetici izni gerektirmeyen TEST derlemesi)" -ForegroundColor Cyan
    $stage = Join-Path $root "build\stage\TurboDM"
    if ($stage.Length -gt 90) { $stage = Join-Path $env:LOCALAPPDATA "TurboDM-build\stage\TurboDM" }
    if (-not (Test-Path $stage)) { Write-Warning "Önce build.ps1 çalıştırın"; $failed++ }
    else {
        $out = powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\test_installer.ps1" -Project $root -Stage $stage
        $out
        $bad = $out | Where-Object { $_ -match "kaldı mı: True|hepsi tamam: False|exit=[1-9]|korunmuş mu: False|başlatma kaydı: True|dosya sayısı: 0$|klasöründe: False" }
        if ($bad) { Write-Host "Kurulum testinde sorun:" -ForegroundColor Red; $bad; $failed++ }
        Remove-Item -LiteralPath (Join-Path $root "build\test") -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Remove-Item -LiteralPath (Join-Path $root "build\tmp") -Recurse -Force -ErrorAction SilentlyContinue

if ($failed) { Write-Host "BAŞARISIZ: $failed paket" -ForegroundColor Red; exit 1 }
Write-Host "TÜM TESTLER GEÇTİ" -ForegroundColor Green
