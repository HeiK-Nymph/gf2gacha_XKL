# B服登录与构建说明

版本：`0.1.4`，versionCode 12。

添加账号时选择「B服 · 哔哩哔哩」，可以使用手机号验证码，也可以切换账号密码登录。
密码登录先直接请求认证；只有服务端返回安全验证要求时，才展示应用内验证窗口。
用户完成验证后继续本次请求；取消即停止，不自动重试密码。
App直接完成B站短信登录、换取散爆游戏凭证和渠道6的五池查询。发码由用户点击触发；
登录失败不会自动重试。安全请求头由App进程内的原生库生成，不需要ADB、root或代理。

官服原有短信、密码登录保持可用。旧账号文件没有channel字段时按官服读取。
账号按渠道和UID区分：官服沿用原UID键，B服使用`bili:<uid>`键；凭证和记录缓存相互隔离。
续登沿用账号的渠道。B服密码登录使用动态RSA公钥加密，支持手机号、用户名或邮箱作为账号。
B服仍暂不支持导出到小程序，因为当前小程序导入协议没有渠道字段。

## 本地构建输入

SDK应用密钥由未跟踪的`XKL_android/bili.properties`中的`appKey`提供，通过BuildConfig编入APK。
它是SDK客户端配置，不是玩家的登录凭证。玩家手机号、验证码和access_token不参与构建。

以下三个arm64库来自本地B服客户端APK，放在`app/src/main/jniLibs/arm64-v8a/`。
二进制文件和本地密钥配置均由Git忽略。当前测试版只包含arm64 ABI。

| 文件 | SHA-256 |
| --- | --- |
| libcrypto_1_1.so | 21230851fabb183eb2a28300701cabd8bef3739292a85ed07ef5539814949f12 |
| libssl_1_1.so | c4e3624d75df152a8a55ff0697e8b018f77a3c447c8dd6072f01f6220e1d5d33 |
| libcustom_rules.so | 21107551854bf3c9fa42011e480cc9f7d4a6d90a8cbb40f57d1559e8f689e793 |

准备输入：`python tools/prepare_bili_build.py <B服APK> --init-json <包含EXTEND.APP_KEY的本地初始化JSON>`。
脚本只复制上述库和APP_KEY，不复制账号凭证。然后按README使用JDK 17、Android SDK 34和Gradle 8.7构建。

## 协议

- B站发码：`https://line1-sdkcenter-login.bilibiligame.net/api/external/otp/send/v3`。
- B站验证码登录：同主机`/api/external/login/otp/v3`，需要本次发码返回的captcha_key。
- 密码公钥：同主机`/api/external/issue/cipher/v3`，cipher_type=bili_login_rsa。
- 密码登录：同主机`/api/external/login/v3`，RSA/ECB/PKCS1Padding加密hash+密码，Base64密文参与签名。
- 安全验证：同主机`/api/client/start_captcha`，用户完成后补充验证字段，重新签名并提交一次。
- 游戏凭证交换：`https://gf2-zoneinfo.sunborngame.com/bili/login`。
- 抽卡查询：`https://gf2-gacha-record.sunborngame.com/list?game_channel_id=6&type_id=3`。
- 小程序钥匙：携带 `game_channel_id=6`，小程序按同一渠道查询记录和助战网关。
- B站SDK：app_id/game_id 5279、merchant_id 1226、server_id 4424、sdk_ver 5.9.0。
- Mica公共参数：game_channel_id 6、os 1、reyun_channel_id bzaz。

App持久化独立的设备标识，缓存一小时的B站安全头规则；captcha_key随登录页状态保存。
普通登录只保存最终游戏凭证，不保存B站access_key或验证码。
B服密码登录遇到GeeTest滑块或图片验证码时，使用应用内验证窗口。
WebView只接收验证挑战，账号、密码和登录令牌不会传入网页；主页面导航受到限制。
验证窗口取消或页面销毁后不会继续登录。密码输入不随Activity实例状态保存。

## 验证

`assembleRelease`、`assembleReleaseAndroidTest`和`lintRelease`用于构建检查。
新增真机检查使用原有Instrumentation runner：

```
adb shell am instrument -w -e verifyBili true uk.gf2gacha.xkl.test/uk.gf2gacha.xkl.MiniProgramKeyInstrumentation
```

该检查验证旧账号迁移、同UID不同渠道的缓存/凭证隔离、错误短信凭证的本地拒绝，
以及App进程内的原生库加载和SDK配置请求；不会发送短信或读写真实账号存储。

手工测试：添加B服账号、发送验证码、登录、查看五池记录、切回原官服账号并检查缓存。
单会话凭证被其他登录作废时，刷新应继续使用B服的短信续登。


## 发布验证

流程测试覆盖无需验证直接成功、要求验证后继续、取消停止、普通密码错误不弹验证、验证重试边界及RSA编码；
同时检查账号渠道隔离和旧账号兼容。发布APK只包含程序与内置资源，不包含账号文件、验证凭证或研究记录。
