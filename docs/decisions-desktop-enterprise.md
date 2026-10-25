# 桌面端改版决策记录（2026-10-25）

来源：需求拷打会（grill），参与者：项目作者 + ZCode。
状态标记：✅ 已定 ｜ ⏳ 待定。

## ✅ 已定

### D1 「企业级」的定义
**决定：本轮「企业级改造」= 前端 UI 观感改版**，对齐专业桌面应用的质感。日志升级、CI、代码签名、设置框架、i18n 等工程维度本轮不做。
**理由：** 作者明确「想让前端样式变得跟企业级应用一样，至于其他的先不管」。

### D2 技术栈保留
**决定：保留 Python + pywebview + Vue3 + mitmproxy，不换栈。**
**理由：** 抓包链、更新器、协议解析、成堆测试全在 Python 侧；换栈零新用户价值。

### D3 页面结构
**决定：改侧边导航多视图**（总览 = 三~五列卡池；工具 = 证书、日志/运行状态、更新、导出钥匙），顶栏瘦身只留全局状态与当前记录选择。
**理由：** 现顶栏塞 9 个按钮，是观感老旧的主要来源；侧栏结构也是「专业应用」骨架感的关键。

### D4 视觉基调
**决定：暗色底 + 金色低饱和强调**，与安卓端、小程序的「暗金屏」一脉相承，三端品牌统一。
**理由：** 公告弹窗已有「纸感 + 金」自创语言，证明项目有品牌雏形；顺着既有品牌走而非发明新视觉。

### D5 移除 Element Plus，全手写
**决定：去掉 element-plus 依赖（含 @element-plus/icons-vue），组件与设计 token 全手写，以「成果优秀 + 应用体积最小」为优先。**
**理由：** 作者点名体积优先并授权全手写；当前 EP 全量引入体积大；页面规模（单页 + 少量弹窗）手写完全可控。
**约束：** 必须替换所有 EP 用点：ElMessage / ElMessageBox（toast、confirm 自研）、el-select（记录选择）、el-dialog（分享/更新提示/日志/公告）、el-checkbox、el-image 预览（公告图）、el-button、el-row/col（改 CSS grid）、3 个图标（内联 SVG）。
**更新兼容：** 更新器整包替换 `_internal`，前端 dist 变化不影响更新链路；记录 JSON 格式不动；`make_release.py` 发布自检继续校验前端产物存在。旧版用户正常升级无障碍。

### D6 钥匙导出（XKL1）桌面端实现
**决定：**
- 格式照抄安卓 `MiniProgramKey.kt`：`XKL1.` + base64url(JSON `{version:1, uid, credential, game_channel_id}`)，URL_SAFE、无 padding。
- 凭证来源：`json/latest_request.json` 的 Authorization 头。
- 核验照抄安卓全分支：先用**记录接口**核验凭证有效性（官服再 account/info 核对 UID 一致；B 服跳过 account/info，即提交 `4ac803d` 的结论）；核验期间 UID 变化要防串号。
- token payload 解出 `expires`，导出前显示过期时间；过期引导用户开游戏重开「招募 · 访问详情」重新抓包，不做静默降级。
- 钥匙不落盘、不进日志；导出动作 = 用户点按钮复制到剪贴板（Windows 无敏感剪贴板标记，靠显式操作 + 过期警示兜底）。
- 小程序端零改动（import 页 placeholder 已预留「电脑导出」文案，只认粘贴）。

**理由：** 协议坑已被安卓端踩平（`IMPORT_KEY_PROTOCOL.md` 是权威契约），照抄零风险。

### D7 交付编排
**决定：钥匙导出后端先行**（`backend/key_export.py` + pywebview 桥接白名单 + 测试，可独立验证）；**前端界面随 UI 改版用新风格一次画完**，避免样式写两遍。总交付 = 新 UI 与钥匙导出同版上线。
**理由：** 作者确认「后端先行，UI 随改版」。

## ⏳ 待定 / 顺带事项

- **gachaImport 内置 ssr.json 漂移**：小程序云函数内置字典落后源 12 把五星武器（10-13 vs 10-16），这批武器不计五星。修法：跑 `sync_embedded_manifests` + 微信开发者工具重部署云函数。待作者点头。
- **窗口可缩放**：现为 1200×800 固定（`resizable=False`），侧栏布局是否顺势放开缩放，改版时定。
- 记录明细是否独立成视图：当前卡池卡片自带分页，暂不拆，改版时视空间再定。

## 落地记录（2026-10-25 实施补充）

- **D3/D4/D5 已实施**：侧栏壳子（总览/工具）+ 暗金外壳；Element Plus 与 @element-plus/icons-vue、未使用的 axios/qs 全部移除。手写组件层在 `frontend/src/ui/`（按钮/弹窗/toast/confirm/下拉/勾选/灯箱/图标 9 个文件），设计 token 在 `src/styles/tokens.css`（金色取自公告弹窗既有品牌色 #d9a441）。**前端构建产物从 1541KB（1.1.8 发布包实测）降到 344KB**（JS gzip 93KB，约 -78%）。
- 卡池卡片（GachaItem）保持浅色纸面（#fbfaf6 暖白 + 金描边，与公告弹窗同材质），浅色内容卡浮于暗色画布上；分享截图（白底 html2canvas）样式不受影响。
- **D6 已实施**（`backend/key_export.py` + `main.py` 桥接 + `test_key_export.py` 12 项测试）。实现中确认的补充细节：
  - access_token payload 只有 openid/expires/is_guest/tinx、**没有 uid**（协议文档 §6），PC 端又没有登录能力，所以 **B服（渠道 6）导出必须由用户在界面补填游戏 UID**（小程序端对 B服钥匙同样无法复核 UID，信任级别等价）；官服 UID 由 account/info 核对。
  - 渠道判定：读捕获请求 query params 里的 `game_channel_id`（params 缺失时看 body，认不出按官服）。
  - 防串号：核验完成后与复制前都复查捕获文件的 Authorization 是否仍是同一份（对应安卓 matchingAccount）。
  - 钥匙只在「复制」动作里现算并写 Win32 剪贴板（ctypes，无新依赖）：不落盘、不进日志、不回传前端 JS。核验通过的暂存只存内存，程序退出即消失。
  - 钥匙导出 UI 在「工具」页：状态预览（捕获/渠道/过期时间）→ 生成导出钥匙（记录接口核验）→ 确认弹窗 → 复制。
- `tools/verify_desktop_lifecycle.py` 的 toast 断言已从 `.el-message` 适配为自研 `.app-toast`；真窗口回归三场景（loading / early-close / fresh-data）全部通过。
- 窗口仍为 1200×800 固定，缩放维持待定。
