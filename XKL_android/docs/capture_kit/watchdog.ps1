# Safety net: if mitmdump disappears while the system proxy points at it, clear the proxy.
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class WNet{[DllImport("wininet.dll",SetLastError=true)]public static extern bool InternetSetOption(IntPtr a,int b,IntPtr c,int d);}'
for ($i = 0; $i -lt 1440; $i++) {
    Start-Sleep -Seconds 5
    $en = (Get-ItemProperty -Path $key -Name ProxyEnable -ErrorAction SilentlyContinue).ProxyEnable
    if ($en -eq 0) { break }
    if (-not (Get-Process mitmdump -ErrorAction SilentlyContinue)) {
        Set-ItemProperty -Path $key -Name ProxyEnable -Value 0
        [WNet]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null
        [WNet]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null
        break
    }
}
