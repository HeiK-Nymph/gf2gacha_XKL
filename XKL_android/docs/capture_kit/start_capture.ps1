# Start capture. Order matters: mitmdump must be LISTENING before the system proxy is enabled.
$kit  = $PSScriptRoot
$repo = Split-Path (Split-Path (Split-Path $kit -Parent) -Parent) -Parent
$certs = Join-Path $repo "certs"
$mitm = "D:\miniconda3\Scripts\mitmdump.exe"
if (-not (Test-Path $mitm)) { $mitm = "mitmdump" }
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"

Get-Process mitmdump -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 800
$p = Start-Process -FilePath $mitm `
  -ArgumentList '--listen-port','8080','--set',"confdir=$certs",'-s',"$kit\capture_addon.py" `
  -RedirectStandardOutput "$kit\mitmdump_out.txt" -RedirectStandardError "$kit\mitmdump_err.txt" `
  -WindowStyle Hidden -PassThru
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", 8080); $c.Close(); $ok = $true; break } catch {}
}
if (-not $ok) { Write-Output "ERROR: mitmdump is not listening. System proxy NOT changed (internet is safe)."; exit 1 }
Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy","Bypass","-File","$kit\watchdog.ps1" -WindowStyle Hidden -RedirectStandardOutput "$kit\watchdog_out.txt" -RedirectStandardError "$kit\watchdog_err.txt"
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class WinINetOn{[DllImport("wininet.dll",SetLastError=true)]public static extern bool InternetSetOption(IntPtr a,int b,IntPtr c,int d);}'
Set-ItemProperty -Path $key -Name ProxyEnable -Value 1
Set-ItemProperty -Path $key -Name ProxyServer -Value "127.0.0.1:8080"
[WinINetOn]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null
[WinINetOn]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null
Write-Output "OK: mitmdump pid=$($p.Id) listening on 8080, system proxy = 127.0.0.1:8080, watchdog armed."
Write-Output "Next: open the game client -> logout -> login -> open the gacha record page -> then run stop_capture.ps1"
