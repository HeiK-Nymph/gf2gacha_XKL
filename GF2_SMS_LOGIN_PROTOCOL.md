# 少前2 追放 — 手机号 + 短信验证码登录协议（逆向记录）

来源：官方 PC 客户端全量抓包 + APK 静态分析
关键类：`com.mica.baselib.utils.MD5U`(simpleSign / sortJOParamsAndMD5SignHaveSeparator)、
`com.mica.micasdk.repository.http.ApiCommon`(addCommonParams)、
`ApiClientRegister`(sendSmsPhoneLogin)、`ApiClientAccount`(phoneSmsLogin)

## 0. 结论
纯手机 App 即可完成：手机号 -> 发码 -> 校码 -> 拿 token -> 查抽卡记录。
不需要 root / VPN / 证书 / 电脑 / 账号密码。签名算法无密钥。

## 1. device_num（客户端自造，本地持久化）
    android_id = Settings.Secure.getString(cr, "android_id")
    device_num = UUID.nameUUIDFromBytes(android_id.getBytes(UTF_8)).toString()
（PC 客户端是 40 位十六进制串；安卓 SDK 是带横线的 UUID 字符串，服务端两者都接受）

## 2. sign 算法（32 位小写 MD5，无盐）
参与签名的字段 = {device_num, timestamp} + 该接口的业务签名字段：
    sign = md5( 按 key 字典序排序后的 "k1=v1&k2=v2&..." )
- 发码接口业务字段：phone_number
- 校码接口业务字段：phone_number
即 md5("device_num=<dn>&phone_number=<phone>&timestamp=<ts>")

## 3. 通用请求头
    Content-Type: application/json      (查记录 /list 用 application/x-www-form-urlencoded)
    User-Agent: UnityPlayer/2019.4.40f1 (UnityWebRequest/1.0, libcurl/7.80.0-DEV)
    X-Unity-Version: 2019.4.40f1

## 4. 通用请求体（android: os=3）
    {"os":3,"reyun_channel_id":"1029","game_channel_id":5,"device_num":"<dn>",
     "timestamp":<秒级>,"language":"cn","area_code":"+86","sign":"<sign>",
     "phone_number":"<phone>","mac":"","x":-1}

## 5. 接口一：发送短信验证码
    POST https://gf2-cn-plateuser.sunborngame.com/sms/phone_login
    body: 通用字段（无 verify_code）
    -> {"code":0,"msg":"OK"}   code!=0 时 msg 为原因（频率限制/号码格式等）

## 6. 接口二：校验验证码并登录
    POST https://gf2-zoneinfo.sunborngame.com/phone/sms_login
    body: 通用字段 + {"verify_code":"<6位>"}
    -> {"code":0,"msg":"OK","data":{
         "access_token":"<base64 payload>.<32字节签名>",
         "uc_account_token":"<base64 payload>.<签名>",
         "uid":389****920,"phone_number":"...","is_guest":0,"is_adult":1,...}}
access_token 的 payload 解码为 {"openid":"...","expires":<epoch>,"is_guest":0,"tinx":9}。

## 7. 接口三：查抽卡记录（直接使用上一步的 access_token）
    POST https://gf2-gacha-record.sunborngame.com/list?game_channel_id=5&type_id=3
    headers: Authorization: <access_token>
    body(form): type_id=<池子>&limit=20&next=<分页游标>
    -> {"code":0,"message":"OK","data":{"list":[...],"next":"..."}}

池子 type_id：1 常驻 / 3 角色 / 4 武器 / 6 自选角色 / 7 自选武器。
每条记录字段：{"pool_id":261001,"item":11036,"time":1786726425,"item_num":1}
（item 是物品 id，五星的名字要查 json/ssr.json 的 SSR_character / SSR_weapon）

### 7.1 分页（已实测）
- 默认每页 6 条；**`limit` 参数有效，上限 20**（limit>20 仍返回 20）。加 limit 后请求数少 3.33 倍。
- `next` 游标格式是 `<time>-<recordId>`（如 `1786726419-1329472`），**伪造游标无效**
  （把 time 改成 1 再带正确 id 会返回空），所以**池内只能串行翻页，池间可以并发**。
- 五个池子并发 + limit=20 实测：**12.1 秒 -> 2.5 秒（快 4.8 倍）**（PC 版每页只有 6 条，所以本 App 比 PC 版还快）。

### 7.2 令牌是单会话的（重要）
同一账号**新登录一次，会让之前的 access_token 立刻作废**：
实测 PC 脚本拿到的 token（负载里 expires 还有 7 天）在手机 App 登录后马上返回 `{"code":-1,"message":"token err"}`。
所以：App 里遇到 `token err` 的正确处理是**提示重新登录**，而不是当成网络故障。

### 7.3 辅助接口
    GET https://gf2-zoneinfo.sunborngame.com/account/info  + 同 Authorization  可取 uid

## 8. 注意
- 这是模拟官方客户端登录的第三方实现，账号安全与风控责任在 App 方；device_num 建议每台设备固定一个。
- 短信发码接口切勿自动化批量调用（法律与滥用风险），必须用户手动点击并做频率限制。
- 手机号只在本地用于发码/登录，不要上传自建服务器留存。
- 游戏更新后协议可能变化：用 docs/capture_kit 重新抓一次对照更新。
