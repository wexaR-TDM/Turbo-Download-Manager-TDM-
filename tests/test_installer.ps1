# Kurulum → öz-test → sahte kullanıcı verisi → kaldırma → iz kontrolü (yönetici izni gerektirmeyen TEST derlemesiyle)
param([string]$Project, [string]$Stage)
$ErrorActionPreference = "Stop"
$origAppData = $env:APPDATA  # gerçek TurboDM'i kapatıp açarken kullanılır
$sp = $PSScriptRoot
$out = Join-Path $Project "build\test"   # proje içinde; test bitince silinir
New-Item -ItemType Directory -Force $out | Out-Null
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
& $iscc /Q "/DStage=$Stage" "/DTestMode" "/DTestOut=$out" "$Project\installer\TurboDM.iss"
if ($LASTEXITCODE) { throw "ISCC test derlemesi başarısız" }
$setup = "$out\TurboDM-Setup-TEST.exe"
$app = "$env:LOCALAPPDATA\TurboDM-Test"

# Gerçek kullanıcı verisine dokunmamak için sahte APPDATA
$fakeAppData = "$out\fake_appdata"
$fakeDl = "$out\fake_downloads\TurboDM"
New-Item -ItemType Directory -Force "$fakeAppData\TurboDM", "$fakeDl\Video" | Out-Null
$env:APPDATA = $fakeAppData

function RealReg {
    # bu bilgisayardaki GERÇEK TurboDM kurulumunun kayıtları: test bunları değiştirmemeli
    $c = "HKCU:\Software\Classes"
    @((Get-ItemProperty "$c\.torrent" -ErrorAction SilentlyContinue)."(default)",
      (Get-ItemProperty "$c\TurboDM.torrent\shell\open\command" -ErrorAction SilentlyContinue)."(default)",
      (Get-ItemProperty "$c\magnet\shell\open\command" -ErrorAction SilentlyContinue)."(default)",
      (Get-ItemProperty "HKCU:\Software\RegisteredApplications" -ErrorAction SilentlyContinue).TurboDM) -join " | "
}
$realBefore = RealReg

# Bu bilgisayarda gerçek TurboDM açıksa: test kurulumu onu da kapatırdı (aynı tek-örnek kilidi). Önce düzgünce
# kapat (indirmelerin yeri kaydedilir), test bitince görev çubuğunda yeniden aç (inmekte olanlar sürer).
$realExe = $null
$real = Get-Process TurboDM -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -notlike "*TurboDM-Test*" } | Select-Object -First 1
if ($real) {
    $realExe = $real.Path
    $fake = $env:APPDATA; $env:APPDATA = $origAppData
    Start-Process $realExe -ArgumentList "--quit" -Wait
    $env:APPDATA = $fake
    for ($i = 0; $i -lt 40 -and (Get-Process -Id $real.Id -ErrorAction SilentlyContinue); $i++) { Start-Sleep 0.25 }
    "   (gerçek TurboDM test süresince kapatıldı)"
}

if (Test-Path "$app\unins000.exe") { Start-Process "$app\unins000.exe" -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES" -Wait; for ($i = 0; $i -lt 30 -and (Test-Path $app); $i++) { Start-Sleep 0.5 } }
"== 1) Sessiz kurulum"
$p = Start-Process $setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/TASKS=desktopicon", "/LANG=german", "/LOG=`"$out\install.log`"" -PassThru -Wait
"   exit=$($p.ExitCode)"
"   kurulu dosya sayısı: " + (Get-ChildItem $app -Recurse -File).Count
"   kurulum dili ayarlarda: " + ((Get-Content "$fakeAppData\TurboDM\settings.json" -Raw -ErrorAction SilentlyContinue) -match '"language":\s*"de"')
"   dile göre eklenti yardımı (BROWSER_EXTENSION.txt): " + (Test-Path "$app\BROWSER_EXTENSION.txt")
"   unins000.exe programın klasöründe: " + (Test-Path "$app\unins000.exe")
"   ffmpeg: " + (Test-Path "$app\ffmpeg\ffmpeg.exe") + " | eklenti: " + (Test-Path "$app\browser_extension\manifest.json")
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "TurboDM-Test"
"   Başlat menüsü kısayolları: " + ((Get-ChildItem $startMenu -ErrorAction SilentlyContinue).Name -join ", ")
$desk = [Environment]::GetFolderPath("Desktop")
"   masaüstü kısayolu: " + (Test-Path "$desk\TurboDM-Test.lnk")
$unKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{0C4B1D2E-7E57-4E8A-A6F1-2D5C8B9E0F17}_is1"
"   'Programlar ve Özellikler' kaydı: " + (Test-Path $unKey) + " → " + (Get-ItemProperty $unKey).DisplayName

"== 2) Kurulu programın öz-testi"
& "$sp\clean_run.ps1" -Exe "$app\TurboDM.exe" -Arguments "--selftest `"$out\selftest_installed.json`""
$st = Get-Content "$out\selftest_installed.json" -Encoding utf8 | ConvertFrom-Json
"   hepsi tamam: " + $st.hepsi_tamam + " | ffmpeg: " + $st.ffmpeg.info.Split("|")[0]
"   youtube: " + $st.youtube.ok + " | " + $st.youtube.info

"== 3) Sahte kullanıcı verisi oluştur, programı başlat (veriyi yüklesin)"
Set-Content "$fakeDl\Video\film.mkv.tdm" "yarim" ; Set-Content "$fakeDl\Video\bitmis.mp4" "tamam"
$items = @(
  @{ id = "a"; kind = "http"; path = "$fakeDl\Video\film.mkv"; status = "stopped"; size = 100; segments = @(,@(0, 99, 5)) },
  @{ id = "b"; kind = "http"; path = "$fakeDl\Video\bitmis.mp4"; status = "completed" }
) | ConvertTo-Json -Depth 5
New-Item -ItemType Directory -Force "$fakeAppData\TurboDM", "$fakeDl\Video" | Out-Null
Set-Content "$fakeDl\Video\film.mkv.tdm" "yarim" ; Set-Content "$fakeDl\Video\bitmis.mp4" "tamam"
[IO.File]::WriteAllText("$fakeAppData\TurboDM\downloads.json", $items)
[IO.File]::WriteAllText("$fakeAppData\TurboDM\settings.json", (@{ download_root = $fakeDl } | ConvertTo-Json))
$procId = & "$sp\clean_run.ps1" -Exe "$app\TurboDM.exe" -Arguments "--tray" -NoWait
Start-Sleep 5
"   çalışıyor (ping): " + (Invoke-RestMethod http://127.0.0.1:9614/ping).app
"   Başlat menüsü kısayolları: " + ((Get-ChildItem $startMenu -ErrorAction SilentlyContinue).Name -join ", ")

"== 4) Sessiz kaldırma (program AÇIKKEN) — varsayılan: ayarlar + yarım kalanlar silinir, indirilenler kalır"
$p = Start-Process "$app\unins000.exe" -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -PassThru -Wait
Start-Sleep 3  # kaldırıcı kendini geçici klasöre kopyalayıp oradan çalışır
for ($i = 0; $i -lt 40 -and (Test-Path $app); $i++) { Start-Sleep 0.5 }
"   exit=$($p.ExitCode)"
"   program kapandı mı: " + (-not (Get-Process -Id $procId -ErrorAction SilentlyContinue))

"== 5) İz kontrolü"
"   kurulum klasörü kaldı mı: " + (Test-Path $app)
"   Başlat menüsü klasörü kaldı mı: " + (Test-Path $startMenu)
"   masaüstü kısayolu kaldı mı: " + (Test-Path "$desk\TurboDM-Test.lnk")
"   Programlar ve Özellikler kaydı kaldı mı: " + (Test-Path $unKey)
"   ayarlar (%APPDATA%\TurboDM) kaldı mı: " + (Test-Path "$fakeAppData\TurboDM")
"   yarım indirme (.tdm) kaldı mı: " + (Test-Path "$fakeDl\Video\film.mkv.tdm")
"   tamamlanmış indirme korunmuş mu: " + (Test-Path "$fakeDl\Video\bitmis.mp4")
"   TurboDM kayıt defteri anahtarı kaldı mı: " + (Test-Path "HKCU:\Software\TurboDM\Install")
"   gerçek kurulumun kayıtları korunmuş mu: " + ((RealReg) -eq $realBefore)
"   Windows açılışında başlatma kaydı: " + [bool](Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name TurboDM -ErrorAction SilentlyContinue)

if ($realExe) {
    $env:APPDATA = $origAppData
    Start-Process $realExe -ArgumentList "--minimized", "--resume"
    "   (gerçek TurboDM görev çubuğunda yeniden açıldı)"
}
"   KURULUM TESTİ SONA ERDİ"
