# Project agent notes

## Long-running commands and tool output

- 对可能产生超过 4 KB 输出、运行超过 30 秒、或会反复刷屏的命令，优先使用：

  ```powershell
  tools\run_logged_command.ps1 -Label "test" -Command 'npm test'
  ```

- 完整输出会写入 `.runtime/codex-tool-runs/`，不要提交。
- 工具结果应优先包含状态、关键错误、末尾片段和 artifact 路径，不要把完整日志或 base64 图片塞回对话。
- 查询优先使用 `Select-Object -First`、`rg` 精确匹配、文件路径和摘要；需要全量日志时再按行段读取 artifact。
- 除非用户明确要求，不要修改 `model_context_window`。
