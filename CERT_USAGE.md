# GF2Gacha_XKL 证书使用说明

## 功能概述

本项目使用动态生成的用户唯一证书，确保每个用户的证书都是独一无二的，避免与其他 mitmproxy 工具冲突，提高安全性。

### 核心特性

1. **动态生成**: 首次运行时自动生成用户唯一证书
2. **自动安装**: 支持自动安装到 Windows 受信任的根证书颁发机构
3. **安全隔离**: 每个用户的证书都是唯一的，避免被恶意软件利用
4. **完全卸载**: 支持一键卸载 gf2gacha_XKL 和 mitmproxy 证书

## 证书工作原理

```
┌─────────────────┐
│  首次运行工具   │
│                 │
│ 1. 检查证书     │
│ 2. 不存在则生成 │
│ 3. 生成唯一CA   │
│ 4. 自动安装     │
└─────────────────┘
         │
         ▼
┌────────────────────────┐
│  certs/ 目录           │
│                        │
│  - mitmproxy-ca.pem    │ (私钥+证书)
│  - mitmproxy-ca-cert.pem│ (证书PEM)
│  - mitmproxy-ca-cert.cer│ (证书DER)
│  - mitmproxy-ca-cert.p12│ (证书PKCS12)
└────────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ Windows 证书存储             │
│                              │
│ 受信任的根证书颁发机构       │
│  └─ gf2gacha_XKL_CA_XXXXXX  │
└──────────────────────────────┘
```

## 使用方法

### 1. 首次运行

当你第一次运行 `GF2Gacha_XKL.exe` 时：

- 工具会自动检测是否存在证书
- 如果不存在，会自动生成一个用户唯一的证书
- 证书文件保存在项目目录的 `certs/` 文件夹中
- 证书名称为 `gf2gacha_XKL_CA_XXXXXX` (XXXXXX 是用户唯一ID)

### 2. 安装证书

在前端界面中点击"安装证书"按钮：

- 工具会自动将证书安装到系统受信任的根证书颁发机构
- **需要管理员权限**，可能会弹出UAC提示
- 安装成功后，会显示证书名称和状态

#### 手动安装（备用方案）

如果自动安装失败：

1. 打开 `certs/` 目录
2. 双击 `mitmproxy-ca-cert.cer` 文件
3. 选择"安装证书"
4. 存储位置选择"本地计算机"
5. 证书存储选择"受信任的根证书颁发机构"

### 3. 验证证书安装

点击"检查证书状态"按钮：

- 显示证书是否已安装
- 显示证书有效期
- 显示证书唯一标识

### 4. 卸载证书

点击"卸载证书"按钮：

- 自动卸载 gf2gacha_XKL 证书
- 同时搜索并卸载 mitmproxy 证书（如果存在）
- **需要管理员权限**

#### 手动卸载

如果需要手动卸载：

1. 按 `Win + R`，输入 `certmgr.msc`
2. 导航到"受信任的根证书颁发机构" → "证书"
3. 找到名称为 `gf2gacha_XKL_CA_XXXXXX` 的证书
4. 右键 → 删除

## 文件说明

### 后端文件

- `backend/cert_generator.py` - 证书生成和管理模块
- `backend/proxy.py` - 代理配置（使用自定义证书目录）

### 生成的证书文件

所有证书文件保存在项目根目录的 `certs/` 文件夹中：

| 文件名 | 说明 | 用途 |
|--------|------|------|
| `mitmproxy-ca.pem` | 私钥 + 证书（PEM格式） | mitmproxy 使用 |
| `mitmproxy-ca-cert.pem` | 仅证书（PEM格式） | Linux/macOS 安装 |
| `mitmproxy-ca-cert.cer` | 仅证书（DER格式） | Windows 安装 |
| `mitmproxy-ca-cert.p12` | PKCS12 格式 | Windows 备用 |

### 前端API

```javascript
// 安装证书
await window.pywebview.api.install_cert();

// 检查证书状态
const status = await window.pywebview.api.check_cert_status();

// 卸载证书
await window.pywebview.api.uninstall_cert();
```

## 测试

运行测试脚本验证功能：

```bash
python test_cert.py
```

测试内容包括：
- 证书生成
- 证书安装
- 证书卸载

## 安全说明

### 为什么使用动态生成证书？

1. **避免冲突**: 每个用户的证书都是唯一的，不会被其他 mitmproxy 实例利用
2. **安全隔离**: 恶意软件无法预测证书路径和名称
3. **隐私保护**: 证书包含用户唯一ID，便于追踪问题但不泄露个人信息

### 证书安全性

- 使用 2048 位 RSA 密钥
- SHA256 签名算法
- 有效期 10 年
- 符合 X509v3 标准
- 包含必要的扩展字段（Key Usage, Basic Constraints）

### 最佳实践

1. **不要在公共环境使用**: 避免在网吧、公共电脑等环境使用
2. **及时卸载**: 使用完毕后卸载证书
3. **定期更新**: 关注项目更新，及时更新工具
4. **保护私钥**: `certs/mitmproxy-ca.pem` 包含私钥，不要分享给他人

## 常见问题

### Q: 安装证书时提示需要管理员权限？

A: 这是正常的，安装到系统受信任的根证书颁发机构需要管理员权限。请点击"是"或输入管理员密码。

### Q: 证书安装成功了，但浏览器还是提示不安全？

A: 请尝试：
1. 关闭浏览器并重新打开
2. 清除浏览器缓存
3. 重启电脑

### Q: 可以同时安装多个 gf2gacha_XKL 证书吗？

A: 每个用户生成的证书是唯一的，可以在不同电脑上安装。但不建议在同一台电脑上安装多个。

### Q: 卸载证书后需要重启吗？

A: 建议重启浏览器或应用程序，某些程序可能需要重启才能完全生效。

### Q: 证书过期了怎么办？

A: 删除 `certs/` 目录，重新运行工具会自动生成新证书。

### Q: 证书文件可以备份吗？

A: 可以备份 `certs/` 目录，在其他电脑上使用相同的证书。但不建议这样做，因为会失去唯一性保护。

### Q: 如何确认证书是我的？

A: 查看证书详细信息中的"公用名"，应该包含 `gf2gacha_XKL_CA_` 和用户唯一ID。

## 技术细节

### 证书生成流程

```python
from backend.cert_generator import ensure_ca_certificate, generate_user_ca_certificate

# 检查并生成证书
cert_dir, is_new = ensure_ca_certificate()
if is_new:
    cert_dir = generate_user_ca_certificate()
```

### 证书安装流程

```python
from backend.cert_generator import install_certificate_windows

# 安装证书
cert_path = cert_dir / "mitmproxy-ca-cert.cer"
success = install_certificate_windows(cert_path)
```

### 证书卸载流程

```python
from backend.cert_generator import uninstall_certificate_windows

# 卸载证书
success = uninstall_certificate_windows("gf2gacha_XKL_CA_XXXXXX")
```

## 版本更新

当更新工具时：

1. 旧版本的证书仍然有效
2. 不需要重新生成证书
3. 如果证书被删除，新版本会自动生成

## 支持与反馈

如有问题，请：
1. 检查 `logs/` 目录下的日志文件
2. 在 GitHub 提交 Issue
3. 提供证书名称和错误信息

---

**注意**: 本工具仅用于学习和研究目的，请遵守相关法律法规。
