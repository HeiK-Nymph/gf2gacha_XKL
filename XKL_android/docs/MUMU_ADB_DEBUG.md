# MuMu ADB 调试指南

通过本机 MuMu 模拟器运行、安装和调试安卓端，不需要连接手机 USB。
以下命令使用 PowerShell。本项目日常调试使用已签名的 release 包，保留与正式版一致的包名与签名。

## 已验证环境

2026-10-16 实测：

- MuMu 系统 Android 12，设备型号返回 `2201123C`。
- MuMu 网络信息显示 ADB 调试端口 `5557,16416`，本机连接 `127.0.0.1:16416` 成功。
- 安装 `0.1.2`（`versionCode=10`）成功，启动后正常进入登录页，应用进程存在。

端口可能随实例或 MuMu 版本变化，**以当前实例显示的端口为准**，不要假定所有机器都是 `16416`。
连接使用本机回环地址 `127.0.0.1`，不用网络信息中的出口 IP、DNS 或 MAC 地址。

## 开启并连接

1. 启动 MuMu 实例，在设置中开启 ADB 调试。
2. 查看当前实例的网络信息，记录 ADB 调试端口。
3. 用项目 Android SDK 自带的 ADB 连接：

```powershell
$adbPath = 'D:\android-sdk\platform-tools\adb.exe'
$mumuSerial = '127.0.0.1:16416' # 换成当前实例的实际端口
& $adbPath connect $mumuSerial
& $adbPath devices -l
& $adbPath -s $mumuSerial shell getprop ro.build.version.release
```

出现 `connected to 127.0.0.1:16416`，且设备列表对应状态为 `device`，即可继续。
后续命令始终带 `-s $mumuSerial`，避免同时连接手机或多个实例时装错设备。

## 构建、安装并启动

```powershell
Set-Location 'D:\myproject\gf2gacha_XKL\XKL_android'
$env:JAVA_HOME = 'D:\java\jdk-17'
$env:ANDROID_HOME = 'D:\android-sdk'
& 'D:\gradle-8.7\bin\gradle.bat' :app:assembleRelease --console=plain
if ($LASTEXITCODE -ne 0) { throw '构建失败，停止安装' }

$apkPath = 'D:\myproject\gf2gacha_XKL\XKL_android\app\build\outputs\apk\release\app-release.apk'
& $adbPath -s $mumuSerial install -r $apkPath
if ($LASTEXITCODE -ne 0) { throw '安装失败，请交由用户手动安装，不修改版本绕过' }
& $adbPath -s $mumuSerial shell am start -W -n uk.gf2gacha.xkl/.ui.MainActivity
```

调试新代码时使用上面的最新构建产物。正式交付目录是
`D:\myproject\gf2gacha_XKL\release`，不能把尚未同步的旧交付包误当作刚构建的新包。
需要同步交付文件时，在仓库根目录运行已有脚本（不会上传 R2）：

```powershell
Set-Location 'D:\myproject\gf2gacha_XKL'
& 'D:\miniconda3\python.exe' tools\make_release.py --android --version 0.1.2 --notes '填写本次更新说明'
```

输出为 `release/gf2gacha_XKL_android.apk` 和 `release/version_android.json`。
`--version` 必须与实际构建版本一致；这里的 `0.1.2` 是本轮开发版本示例。

首次在模拟器安装不会继承真实手机中的账号或记录，需要自行登录。
当前版本未登录时停留在抽卡页；点击「添加账号」，或在刷新/导出提示中确认添加账号后，才进入登录页。

## 检查运行状态与日志

```powershell
& $adbPath -s $mumuSerial shell dumpsys package uk.gf2gacha.xkl |
    Select-String 'versionCode=|versionName='
& $adbPath -s $mumuSerial shell pidof uk.gf2gacha.xkl

# 只查看当前应用进程的日志；Ctrl+C 结束日志跟踪
$appProcessId = (& $adbPath -s $mumuSerial shell pidof uk.gf2gacha.xkl).Trim()
if ($appProcessId) {
    & $adbPath -s $mumuSerial logcat "--pid=$appProcessId"
}
```

不要把含账号、凭证或导入钥匙的日志、截图提交进仓库。

## 版本规则和常见问题

- 开始下一版更新时，`versionName` 和 `versionCode` 各升一次，让旧版用户能检测到更新。
  本轮固定为 `0.1.2 / 10`；正式提交前的重复调试构建沿用这一版，不为了安装反复涨版本。
- 连接被拒绝：确认实例已启动、ADB 已开启、端口正确。同一动作失败两次后停止重复尝试，检查配置或报告问题。
- 设备 `offline`：先对该实例执行 `adb disconnect 127.0.0.1:16416`，再按实际端口重新连接。
- `more than one device/emulator`：给命令补上 `-s $mumuSerial`。
- 安装失败，包括签名不一致或版本降级：停止自动安装，请用户手动安装或处理已有包；
  不自动卸载、不清账号数据、不通过递增版本绕过问题。
- 模拟器重启后如连接失效，重新查看端口并执行 `adb connect`。
- debug 包名为 `uk.gf2gacha.xkl.test`，与 release 的账号数据独立；本指南命令针对 release 包。

## 结束调试

```powershell
& $adbPath disconnect $mumuSerial
```

只断开当前实例，不执行影响其他设备的 `adb kill-server`。
