# Stop capture. Order matters: clear the proxy FIRST, then kill mitmdump.
$kit = $PSScriptRoot
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class WinINetOff{[DllImport("wininet.dll",SetLastError=true)]public static extern bool InternetSetOption(IntPtr a,int b,IntPtr c,int d);}'
Set-ItemProperty -Path $key -Name ProxyEnable -Value 0
[WinINetOff]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null
[WinINetOff]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null
Start-Sleep -Milliseconds 500
Get-Process mitmdump -ErrorAction SilentlyContinue | Stop-Process -Force
$n = (Get-ChildItem -LiteralPath (Join-Path $kit "flows") -File -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Output "OK: system proxy disabled, mitmdump stopped, captured files = $n"
