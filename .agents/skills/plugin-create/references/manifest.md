# Manifest 规则

唯一数据源是 `plugins/<name>/.codex-plugin/plugin.json`。`sync` 据此生成 Claude Code 的 `.claude-plugin/plugin.json` 与 WorkBuddy 的 `.codebuddy-plugin/plugin.json`，并由 `check` 校验。

WorkBuddy 按 `.codebuddy-plugin`、`.workbuddy-plugin`、`.claude-plugin` 的顺序读取第一个找到的清单，所以它只看生成的 `.codebuddy-plugin/plugin.json`。这份清单只含 `name`、`version`、`description`、`author`、`homepage`、`repository`、`license`、`keywords`、`skills` 与 `mcpServers`，路径使用 `${CODEBUDDY_PLUGIN_ROOT}`，与 WorkBuddy 内置插件的写法一致。

| 字段 | 规则 | Claude 清单 |
| --- | --- | --- |
| `name` | 小写 kebab-case，等于目录名，发布后不改 | `name` |
| `version` | SemVer，不带 `v`；只用 `plugin_kit.py bump` 修改 | `version` |
| `description` | 一句话，≤500 字 | `description` |
| `author.name` | 作者 | `author` |
| `repository` | `https://github.com/<owner>/<repo>.git`；s-plugins 以它作为安装来源，发布后不改 | `repository` |
| `license` | SPDX 标识（如 `MIT`、`Apache-2.0`），与根目录 `LICENSE` 一致 | `license` |
| `keywords` | 检索关键词 | `keywords` |
| `skills` | 有 `skills/` 时固定为 `"./skills/"` | 不声明，默认扫描 `skills/` |
| `mcpServers` | 有 MCP 时固定为 `"./.codex-mcp.json"` | 转换为内联 `mcpServers` |
| `interface.displayName` | 展示名，≤80 字 | `displayName` |
| `interface.shortDescription` | 一句话卖点，≤240 字，也用于 s-plugins 插件目录 | — |
| `interface.longDescription` | 能力、场景与前置条件，≤1000 字 | — |
| `interface.developerName` | 开发者 | — |
| `interface.category` | 如 `Productivity`、`Developer Tools` | — |
| `interface.websiteURL` | 仓库或文档的 https 地址 | `homepage` |
| `interface.capabilities` | `Read`、`Write`、`Interactive` 中的适用项 | — |
| `interface.defaultPrompt` | 1–3 条典型提示词，每条 ≤128 字 | — |
| `interface.brandColor` | 可选，`#RRGGBB` | — |

s-plugins 市场的条目由发布通知从这些字段生成，`category` 与安装策略由市场仓库管理。

## Claude 专属配置

hooks、`userConfig`、非 stdio 的 MCP server 等 Claude Code 专属内容，写在仓库根目录 `plugin-kit.json` 的 `claude` 对象中（结构与 `.claude-plugin/plugin.json` 相同），`sync` 会深度合并进生成的清单。`claude.mcpServers` 的覆盖同样用于 WorkBuddy（路径改写为 `${CODEBUDDY_PLUGIN_ROOT}`）；只对 WorkBuddy 生效的内容写在 `codebuddy` 对象中，例如 `{"codebuddy": {"mcpServers": {"<server>": {"defer_loading": true}}}}`：

```json
{
  "claude": {
    "hooks": "./hooks/claude-hooks.json"
  }
}
```

引用的文件放在插件目录内，并避开 Claude Code 的默认路径（如 `hooks/hooks.json`），以免与 Codex 的同名配置冲突。
