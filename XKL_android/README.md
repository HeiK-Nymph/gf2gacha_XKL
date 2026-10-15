# XKL_android —— 夏克里助手（Android 版）

> 应用名：**夏克里助手**（`strings.xml` 的 `app_name`，桌面图标名、分享图品牌都读它；
> 相册目录也用同一个名字，见 `MainActivity.kt` 的保存逻辑）

《少女前线2：追放》抽卡记录，**不需要电脑、不需要 root、不需要装证书、不需要 VPN**。

默认用 **手机号 + 短信验证码**登录；如果收不到短信，可以切到**账号密码登录**兜底
（密码只在本机算一次 MD5，不保存、不上传，登录成功后立即丢弃）。

App 内用 **手机号 + 短信验证码**（或账号密码）登录官方账号，拿到 `access_token`
后直接调用官方抽卡记录接口。协议来自官方 PC 客户端抓包 + APK 静态逆向，已用真实报文逐字节验证。

协议细节 → [GF2_SMS_LOGIN_PROTOCOL.md](../GF2_SMS_LOGIN_PROTOCOL.md)

## 访问模型（跟 PC 版一致：直接进抽卡页）

App **没有"必须先登录"这一步**：

1. 打开 App = 直接进抽卡页，用**本地缓存的记录**渲染（换账号、断网都能看）
2. 顶部四个按钮：**添加账号 / 管理账号 / 分享 / 刷新**（没有"退出登录"）
3. 想加账号 → `添加账号` → 手机号 + 验证码（收不到短信就点底部「改用账号密码登录」）
   → 成功后自动成为当前账号并拉一次记录
4. 想换/删账号 → `管理账号` → 列出所有本地账号（各自独立的凭证 + 记录）：**点一行=切换**，行尾 `删除`=删掉该账号（带二次确认）
5. `刷新`：**token 还能用就直接拉**；失效就**自动重新发验证码 + 弹框让你输码续期**
   （续期过程中当前页面的记录一直在，不会清空）

### 多账号数据模型（`files/accounts.json`）

```json
{ "current": "389****920",
  "accounts": [
    { "uid": "...", "phone": "...", "token": "...", "tokenSavedAt": 0,
      "recordsUpdatedAt": 0,
      "records": { "1": [ {"pool_id":1001,"item":1026,"time":1791900031,"item_num":1} ], "3": [...] } } ] }
```

- 每个账号**各自保存** token 和五池原始记录
- 切账号**只切"当前账号"**，其它账号的凭证和记录原样保留（切回来可直接刷新）
- 全部数据只在本机 App 私有目录，不上传任何服务器
- 手机号也存本地 —— 因为"刷新时自动发验证码"需要知道发给谁

## 界面（暗金风格，语义对齐 PC 版）

- 顶部：`UID: 389****920 · 136****5150 · 更新 10-14 20:21 · 凭证有效/已过期`
- `管理账号` 弹窗：●当前账号 + 打码手机号 + 凭证状态 + 更新时间 + 记录条数 + 删除按钮
- 金色**称号**、**总抽卡数 / 平均出金 / 小保不歪%**、标签胶囊
- 四格统计：五星数 / 角色平均 / 武器平均 / 常驻平均
- 五个池子标签页（启动时并发拉好，切页秒开）
- 池子行：`共 N 抽 · 五星 M 个 · 歪 K 个 · 当前垫 X 抽`
- **垫抽行也有进度条**（金色，X/80）
- 五星列表：头像 / 抽数 / 彩条 / **歪标签** / 名字
- **彩条是斜条纹（平行四边形）动画**，参数按例图逐像素标定：
  - 方向 **"\"（左上 → 右下）**，斜度 `slope = 0.8`（例图实测 dx/dy ≈ +0.89 红 / +0.74 绿）
  - 斜条宽 : 间距 = **15dp : 17dp**（周期 32dp ≈ 1.45 倍条高，与例图 38px/26px = 1.46 一致；
    之前的 8dp/7dp 太细太密，已按反馈加粗拉开）
  - 滚动速度 = 周期 / 时长 = 32dp / **1800ms ≈ 17.8 dp/s**（改前是 900ms；周期拉大后没同步改时长会显得快一倍）
  - **深底色 + 同色系浅色斜条**（不是拿白色叠加，那样会发浅）：
    | 档位 | 底色 | 浅条 | 抽数文字（黑底要亮） |
    |---|---|---|---|
    | 欧 ≤30 抽 | `#00B050` | `#92D050` | `#5FD97F` |
    | 常 <60 抽 | `#FFC000` | `#FFD966` | `#FFD166` |
    | 非 ≥60 抽 | `#C00000` | `#C24146` | `#FF8078` |
    | 垫抽金条 | `#D9A93C` | `#EFC964` | `#E8C170` |

    抽数文字单独用一档亮色（条深、字亮）；分享图是**白底**，那边数字仍用深色（深字白底才看得清）。
  - 红/绿两对取自例图实测（`#C00000/#C24146`、`#00B050/#92D050`）
  - 实现 `app/src/main/java/uk/gf2gacha/xkl/ui/StripeDrawable.kt`：`ValueAnimator` 无限循环平移相位，
    首次绘制启动、View 离屏自动 `cancel()`，不会后台空转
- 弹窗（选择账号、验证码续期）统一暗金卡片风：深色圆角 + 金色标题 + 金色按钮

### 分享（照 PC 版方向做的，出图后可发微信/QQ/存相册）

`分享` → 勾选要分享的卡池 → `生成分享图` → 出图后可：

| 按钮 | 行为 |
|---|---|
| 分享到微信 | `ACTION_SEND` + `setPackage("com.tencent.mm")`，定向打开微信图片分享 |
| 分享到 QQ | 同上，`com.tencent.mobileqq` |
| 保存图片 | 存到相册 `Pictures/夏克里助手/`（API 29+ 走 MediaStore，无需权限；≤28 才要写权限） |
| 更多分享 | 走系统分享面板（88 个可分享目标） |

没装微信/QQ 时会自动回退到系统分享面板。

**出图版式（= App 自己的暗金样式，竖版长图）**：
- 一图**只出当前卡池**（要发别的池就切过去再分享一次）
- **宽 360dp × 3 = 1080px**（与手机屏同宽），**高自适应**：图里字号/头像/彩条在 100% 时和 App 里一样大，
  长图不做一屏压缩，交给用户自己缩放（角色池 18 个五星 → 约 1080×3690）
- 内容顺序：品牌名 `夏克里助手` → 称号（大字金色）→ `总抽卡数 / 平均出金 / 小保不歪` →
  标签胶囊 → 四格统计卡 → 池名+统计（与 App 一样自动换行）→ 垫抽行（问号 + 垫抽数 + 金条 + 已垫 N 抽）→
  五星列表（圆形头像 / 抽数 / 彩条 / **歪** / 名字）→ 页脚署名
- **不含 UID 和更新时间**（分享出去不泄露账号信息）
- 颜色阈值与 PC/App 一致：`<30 绿 #66AD68`、`<60 黄 #F0C044`、其余红 `#D66555`
- 武器没有图 → 画「武」占位圈
- **卡池顺序**（界面标签页 + 分享选择）与 PC 一致：角色池 → 武器池 → 常驻池 → 自选角色池 → 自选武器池

### 颜色与「歪」的语义（与 PC 版完全一致）

| 项 | 规则 | 出处 |
|---|---|---|
| 彩条颜色 | `<30 抽 绿 #66AD68` / `<60 抽 黄 #F0C044` / `>=60 抽 红 #D66555` | PC `customColorMethod` |
| 保底 80 抽 | 进度条 `抽数 × 1.25` 满格 = 80 抽 | 同上 |
| **歪** | 五星 id 属于**常驻池五星集合**（`SSR_permanent`）即为歪；常驻池不参与 | PC `isWai` |
| 小保不歪% | `(限定池五星数 - 歪数) / 限定池五星数` | 同上 |
| **武字/头像** | 在限定武器表→武器；在限定人形表→人形；都不在（常驻池物品）→ **5 位 id 是武器、4 位是人形** | PC `isWeaponItem`（逐字对齐） |

### 五星表从 R2 拉（出新角色不用重发版）

```
https://r2.gf2gacha-xkl.uk/ssr.json   ← SSR_character / SSR_weapon / SSR_permanent
```
启动时先拉（约 3KB）→ 成功写入 `files/ssr_cache.json`；失败用本机缓存；再失败用内置 `assets/ssr.json`。
底部会显示当前用的是哪一份（R2 远程 / 本机缓存 / 内置）。

### 图标

由项目根目录的 `favicon_raw.png`（512×512，与 PC 版同一张）生成 5 种密度 × 方/圆两套，
放在 `app/src/main/res/mipmap-*`。

## 性能（实测）

| 方案 | 角色池 840 条 | 五池总耗时 |
|---|---|---|
| 旧：默认每页 6 条 + 池间串行 | 140 页 | 12.1 s |
| 新：`limit=20` + 五池并发（App） | 42 页 | **2.5 s（快 4.8 倍）** |
| **PC 版打同样补丁后** | 42 页 | **2.1 s** |

## 目录

```
XKL_android/
├── app/                        Android 工程（原生 Kotlin + OkHttp + Coil）
├── verify_login.py             PC 端协议验证脚本
├── GF2_SMS_LOGIN_PROTOCOL.md   协议文档（接口 + 签名 + 分页 + 单会话令牌）
├── docs/capture_kit/           游戏更新后重新抓协议用的抓包工具
└── .runtime/                   脚本运行产物（已 gitignore）
```

## 编译 / 安装

```powershell
cd D:\myproject\gf2gacha_XKL\XKL_android
$env:JAVA_HOME  = "D:\java\jdk-17"
$env:ANDROID_HOME = "D:\android-sdk"
D:\gradle-8.7\bin\gradle.bat assembleDebug

D:\android-sdk\platform-tools\adb.exe install -r app\build\outputs\apk\debug\app-debug.apk
```

| 组件 | 位置 / 版本 |
|---|---|
| JDK | `D:\java\jdk-17` |
| Android SDK | `D:\android-sdk`（platforms;android-34、build-tools;34.0.0、platform-tools） |
| Gradle | `D:\gradle-8.7` |
| AGP / Kotlin | 8.5.2 / 1.9.24，compileSdk 34、minSdk 24、targetSdk 34 |

## release 签名版（公开发布用）

密钥库与密码配置放在仓库里但**不进 git**（`.gitignore` 已挡）：

```
XKL_android/keystore/xkl-release.jks      ← 密钥库（丢了就无法给老用户发更新，务必备份）
XKL_android/keystore.properties           ← 密码配置（storeFile / storePassword / keyAlias / keyPassword）
```

| 项 | 值 |
|---|---|
| 别名 | `xkl` |
| 密码 | 见本地 `XKL_android/keystore.properties`（store 与 key 同；**不进 git，也别写进文档/截图**） |
| 证书 | `CN=gf2gacha-xkl, OU=Android, O=XKL, L=Beijing, ST=Beijing, C=CN`，RSA 2048，30 年 |
| 证书 SHA-256 | `948d8c38bb5d24548eca7e26088e7115d53559f5bef5ac5b696257d1c21806dd` |

```powershell
cd D:\myproject\gf2gacha_XKL\XKL_android
$env:JAVA_HOME = "D:\java\jdk-17"; $env:ANDROID_HOME = "D:\android-sdk"
D:\gradle-8.7\bin\gradle.bat assembleRelease
# 产物：app\build\outputs\apk\release\app-release.apk（约 5.0 MB）

D:\android-sdk\build-tools\34.0.0\apksigner.bat verify --print-certs app\build\outputs\apk\release\app-release.apk
```

**发新版本时**：改 `app/build.gradle.kts` 的 `versionCode`（必须**递增**，否则装不上）+ `versionName`，再 `assembleRelease`。

⚠️ debug 版与 release 版**签名不同**：互相覆盖安装会报 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`，必须先卸载；
卸载会连同 App 私有的 `files/accounts.json`（账号 + 令牌 + 本地记录）一起清掉，需要重新短信登录一次。

## 检查更新（App 内）

标题右边有 **「检查更新」按钮**，另外**启动后会静默查一次**（没网、还没发布，都不打扰用户）。
有新版时弹窗写明「当前版本 → 新版本（大小）+ 更新说明」，按钮文字会变成「有新版本 x.y.z」。

| 用途 | 地址 |
|---|---|
| 检查文件 | `https://r2.gf2gacha-xkl.uk/version_android.json` |
| 安装包 | `https://r2.gf2gacha-xkl.uk/gf2gacha_XKL_android.apk`（**固定文件名**，不带版本号） |

`version_android.json` 的字段名和 PC 的 `version.json` **完全一致**：

```json
{ "current_version": "0.1.1",
  "version_url":    "https://r2.gf2gacha-xkl.uk/version_android.json",
  "download_url":   "https://r2.gf2gacha-xkl.uk/gf2gacha_XKL_android.apk",
  "sha256": "……", "size": 5297387, "update_info": "这次改了什么" }
```

### 发一个新版本

```powershell
# 1. 先改 XKL_android/app/build.gradle.kts：versionCode 必须递增（否则系统不给覆盖安装）+ versionName
cd D:\myproject\gf2gacha_XKL
D:\gradle-8.7\bin\gradle.bat -p XKL_android assembleRelease
# 2. 生成要上传的两个文件（APK 拷成固定名 + json，sha256/size 自动算，避免手工算错）
D:\miniconda3\python.exe tools\make_release.py --android --version 0.1.1 --notes "修了 xxx"
# 3. 上传到 R2 根目录：先传 gf2gacha_XKL_android.apk，最后传 version_android.json
```

**上传顺序不能反**：先传 json 会让用户读到新版本号却下不到包（404 / 校验失败）。

安全设计：只在用户点「立即更新」后才下载 → 边下边算 sha256，跟 json 里对不上就删掉重下（防半包）
→ 交给**系统安装器**（签名不一致系统自己拒绝，装不坏已装的版本）。Android 8+ 首次需要用户允许一次
「安装未知应用」，App 会先弹窗解释再跳系统设置页；装好后再点一次即可，安装包已缓存不会重复下载。

### 真机自测更新链路（不用真的发布）

调试包的 `applicationId` 带 `.test` 后缀（能和正式版**共存**，不会动正式版的账号数据），
且检查地址指向 `http://127.0.0.1:8000/...`：

```powershell
cd D:\myproject\gf2gacha_XKL\XKL_android
D:\gradle-8.7\bin\gradle.bat assembleDebug
D:\android-sdk\platform-tools\adb.exe install -r app\build\outputs\apk\debug\app-debug.apk
D:\android-sdk\platform-tools\adb.exe shell appops set uk.gf2gacha.xkl.test REQUEST_INSTALL_PACKAGES allow
D:\android-sdk\platform-tools\adb.exe reverse tcp:8000 tcp:8000
# .runtime\update_test\ 里放：
#   version_android.json   （current_version 比本机高，sha256/size 指向下面那个 apk）
#   gf2gacha_XKL_android.apk（就是刚构建的 debug apk）
D:\miniconda3\python.exe -m http.server 8000 --bind 127.0.0.1 --directory .runtime\update_test
# 打开 App → 点「检查更新」→ 立即更新 → 应该拉起系统安装器
# 把 json 里的 sha256 改坏再试一次 → 应该提示「完整性校验没通过」且不弹安装器
```

## 已知限制 / 待办

- 分享图是静态长图，条纹不带滚动（要的话可以加同款静态斜纹）。

1. 非五星记录只显示 `#itemId` —— **有意为之**：只有五星需要名字和头像。
2. 账号可在「管理账号」里删除（带二次确认；删的是当前账号时自动切到剩下的第一个；全删光则回到空态）。
3. 令牌是**单会话**的：同账号在游戏内 / PC 版 / 别处再登录一次，旧令牌就作废 —— 所以"刷新"会经常需要重新收码。
   若之后确认游戏每次启动都会顶掉令牌，可研究用登录响应的 `uc_account_token` 做无短信续期。
4. 发布分发用 release 签名版（`release\gf2gacha_XKL_android.apk`），更新走 App 内的「检查更新」。
5. 分享图里的头像需要实时从 R2 下载（29 个五星约 1 秒），网络差时会退化成「？」占位圈。
6. 记录接口只保留一段时间的记录，所以本地记录**只增不减**（按 fakeId 合并，和 PC 版一致）；
   翻页仍是从第 1 页全量翻到 `next` 为空，不做提前停（少翻一页就可能漏记录）。

## 注意事项

1. `device_num` 每台设备固定一个，别每次随机。
2. 短信发码接口**禁止自动化批量调用**，必须用户手动点击 + 频率限制（App 已做 60 秒倒计时）。
3. 手机号、令牌、记录都只在本机，不上传自建服务器。
   账号密码登录时，明文密码只在内存里活一次（算完 MD5 就丢），不落盘、不进日志。
4. 这是模拟官方客户端登录的第三方实现，账号风控责任在 App 方。
