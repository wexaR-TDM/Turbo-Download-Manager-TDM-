# TurboDM.exe'yi Python'suz, sade bir ortamda çalıştırır (başka bilgisayarı taklit).
param([string]$Exe, [string]$Arguments, [int]$TimeoutSec = 120, [switch]$NoWait)
$psi = New-Object Diagnostics.ProcessStartInfo $Exe, $Arguments
$psi.UseShellExecute = $false
$psi.WorkingDirectory = $env:SystemRoot
$psi.EnvironmentVariables["PATH"] = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0"
foreach ($k in @($psi.EnvironmentVariables.Keys)) { if ($k -match "^(PYTHON|QT_|PYSIDE)") { $psi.EnvironmentVariables.Remove($k) } }
$p = [Diagnostics.Process]::Start($psi)
if ($NoWait) { $p.Id; return }
if (-not $p.WaitForExit($TimeoutSec * 1000)) { "TIMEOUT"; $p.Kill(); return }
"exit=" + $p.ExitCode
