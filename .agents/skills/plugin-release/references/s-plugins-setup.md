# 配置 s-plugins 推送

插件发布后，`release.yml` 的 `notify-s-plugins` job 向 `tadazly/s-plugins` 发送 `plugin-released` repository dispatch，市场仓库据此更新 Codex、Claude Code、WorkBuddy 三份市场清单。每个插件仓库配置一次即可：

1. 创建 fine-grained personal access token（GitHub → Settings → Developer settings → Fine-grained tokens）：
   - Resource owner：`tadazly`
   - Repository access：Only select repositories → `tadazly/s-plugins`
   - Permissions：Repository permissions → Contents：Read and write
   - 设置过期时间；过期后重新生成并更新 Secret。
2. 把 Token 保存为插件仓库的 Actions Secret：

   ```bash
   gh secret set S_PLUGINS_DISPATCH_TOKEN --repo <owner>/<repo>
   ```

   命令会提示粘贴 Token。不要把 Token 写进命令参数、文件或日志。
3. 可选：设置 Secret `PLUGIN_KIT_FORBIDDEN`，值为逗号分隔的内部域名、内部品牌词等。CI 与发布流程会拒绝包含这些词的文件，日志中不回显具体的词。
4. 可选：目标市场不是 `tadazly/s-plugins` 时，设置仓库变量 `S_PLUGINS_REPOSITORY=<owner>/<repo>`，并同步修改 `scripts/plugin_kit.py` 顶部的 `MARKETPLACE_REPOSITORY` 与 `MARKETPLACE_NAME`（README 安装章节会用到）。

首次发布会在 s-plugins 自动登记插件。payload 由 `python scripts/plugin_kit.py payload --ref vX.Y.Z` 从 manifest 生成，包含 `name`、`version`、`description`、`source`（manifest `repository`、`./plugins/<name>`、tag）与展示信息。登记后，`repository` 与插件路径不能再通过通知修改；确需迁移时，在 s-plugins 仓库人工修改。
