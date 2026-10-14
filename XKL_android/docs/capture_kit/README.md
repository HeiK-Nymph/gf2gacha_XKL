# capture_kit —— 游戏更新后重新采集协议

用途：游戏版本更新后协议字段/签名可能变化，用这套工具重新抓一次「登录 + 抽卡记录」流量，
      再对照 `../../GF2_SMS_LOGIN_PROTOCOL.md` 更新文档。

工具链：mitmproxy（`mitmdump`，需在 PATH 或放在 `D:\miniconda3\Scripts\`）+ 项目 `certs/` 目录里已有的 CA
（该 CA 你 PC 版早就装进 Windows 受信任根了，不用重装）。

## 步骤

```powershell
# 1) 开始采集（会临时把 Windows 系统代理指向 127.0.0.1:8080；脚本会先确认 mitmdump 已监听才改代理）
powershell -ExecutionPolicy Bypass -File .\start_capture.ps1

# 2) 游戏客户端里：退出登录 -> 用「手机号 + 短信验证码」登录 -> 进「招募 -> 访问详情」停 20 秒

# 3) 停止采集（先撤代理再杀进程；也可以用看门狗兜底：mitmdump 一挂就自动撤代理）
powershell -ExecutionPolicy Bypass -File .\stop_capture.ps1
```

## 产物

- `flows\NNN_req|res_<host>.json`：命中域名（sunborn/mica/passport/tersafe/turing/midas）的完整报文
- `hosts.txt`：所有出现过的 SNI（含被透传未记录的）

⚠️ `flows\` 里有**账号凭证和 token**，分析完请删掉，别提交到 git（已加进 .gitignore）。

## 排查

- 看 `mitmdump_out.txt` / `mitmdump_err.txt`
- 电脑上网异常：直接跑 `stop_capture.ps1`（它先撤代理）
