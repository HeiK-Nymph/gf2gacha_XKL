# GF2Gacha_XKL 证书功能快速开始

## 概述

本项目现在支持动态生成用户唯一的证书，自动安装到系统，并提供完整的卸载功能。

## 核心改进

### 1. 动态证书生成 ✅
- **首次运行**时自动生成用户唯一证书
- 证书名称为：`gf2gacha_XKL_CA_XXXXXX`（每个用户不同）
- 保存在项目目录的 `certs/` 文件夹中
- **不会**打包预生成的证书

### 2. 自动安装 ✅
- 点击"安装证书"按钮自动安装到系统
- 安装到：受信任的根证书颁发机构
- **需要管理员权限**（会弹出UAC提示）

### 3. 证书状态检查 ✅
- 点击"检查证书"按钮查看安装状态
- 显示证书是否已安装
- 显示证书有效期

### 4. 一键卸载 ✅
- 点击"卸载证书"按钮
- 自动卸载 gf2gacha_XKL 证书
- 同时卸载 mitmproxy 证书（如果存在）
- **需要管理员权限**

## 文件结构

```
gf2gacha_XKL/
├── backend/
│   ├── cert_generator.py      # 证书生成和管理（新增）
│   ├── proxy.py               # 代理配置（已修改）
│   └── ...
├── frontend/
│   └── src/
│       └── App.vue            # 前端界面（已修改）
├── certs/                     # 证书目录（自动生成，已加入.gitignore）
│   ├── mitmproxy-ca.pem
│   ├── mitmproxy-ca-cert.pem
│   ├── mitmproxy-ca-cert.cer
│   └── mitmproxy-ca-cert.p12
├── requirements.txt           # Python依赖（新增）
├── .gitignore                 # Git忽略规则（已更新）
├── CERT_USAGE.md              # 详细使用文档（新增）
└── test_cert.py               # 测试脚本（新增）
```

## 使用流程

### 首次使用

1. **运行程序**
   ```bash
   python main.py
   ```

2. **自动生成证书**
   - 控制台显示：`[CERT] 首次运行，生成用户专属证书...`
   - 证书保存在 `certs/` 目录

3. **安装证书**
   - 点击界面上的"安装证书"按钮
   - 弹出UAC提示，点击"是"
   - 安装成功提示："证书安装成功！"

4. **验证安装**
   - 点击"检查证书"按钮
   - 确认显示"证书已安装"

5. **开始使用**
   - 点击"更新记录"获取抽卡数据

### 卸载证书

1. **点击卸载**
   - 点击"卸载证书"按钮
   - 确认对话框中点击"确定"
   - 弹出UAC提示，点击"是"

2. **验证卸载**
   - 点击"检查证书"按钮
   - 确认显示"证书未安装"

## API 接口

### 后端 Python API

```python
# 安装证书
install_cert() -> {
    "status": "success|error",
    "msg": "消息",
    "cert_name": "证书名称"
}

# 检查证书状态
check_cert_status() -> {
    "status": "success|error",
    "installed": True|False,
    "cert_name": "证书名称",
    "valid_from": "开始时间",
    "valid_to": "结束时间"
}

# 卸载证书
uninstall_cert() -> {
    "status": "success|error",
    "msg": "消息",
    "details": [...]
}
```

### 前端 JavaScript API

```javascript
// 安装证书
await window.pywebview.api.install_cert()

// 检查证书状态
await window.pywebview.api.check_cert_status()

// 卸载证书
await window.pywebview.api.uninstall_cert()
```

## 测试

运行测试脚本验证所有功能：

```bash
python test_cert.py
```

测试内容：
- ✅ 证书生成
- ✅ 证书安装
- ✅ 证书状态检查
- ✅ 证书卸载

## 安全特性

1. **唯一性**: 每个用户生成的证书都不同
2. **隔离性**: 不与系统 mitmproxy 冲突
3. **可卸载**: 提供完整的卸载功能
4. **透明性**: 证书信息完全可见

## 注意事项

1. **管理员权限**: 安装/卸载证书需要管理员权限
2. **首次运行**: 首次运行会自动生成证书
3. **证书备份**: 备份 `certs/` 目录可在重装后恢复
4. **多设备**: 每个设备生成的证书不同

## 常见问题

**Q: 证书安装失败？**
A: 确保以管理员身份运行程序

**Q: 如何确认证书已安装？**
A: 点击"检查证书"按钮，或使用 `certmgr.msc` 查看

**Q: 可以手动安装证书吗？**
A: 可以，双击 `certs/mitmproxy-ca-cert.cer` 手动安装

**Q: 证书过期怎么办？**
A: 删除 `certs/` 目录，重新运行程序会自动生成新证书

## 完整文档

查看 `CERT_USAGE.md` 获取更详细的说明。

---

**版本**: 1.0.0  
**最后更新**: 2026-03-22
