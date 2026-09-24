# AGENTS.md

## 仓库定位

- 基于 plugin-template 的单插件仓库。插件同时支持 Codex、Claude Code 与 WorkBuddy，发布后登记到 [s-plugins](https://github.com/tadazly/s-plugins) 市场。
- 可分发的插件放在 `plugins/<name>/`；源码、测试、脚本与文档放在仓库根目录。
- 如果 `plugins/example-plugin/` 仍存在，说明仓库尚未初始化：先按 plugin-create 技能运行 `init`。

## 任务与技能

| 任务 | 技能 |
| --- | --- |
| 按需求制作插件，增改 Skill 或 MCP 工具 | `.agents/skills/plugin-create` |
| 生成或更新 README | `.agents/skills/plugin-readme` |
| 发布版本、配置 s-plugins 推送、处理发布故障 | `.agents/skills/plugin-release` |

技能正文只在 `.agents/skills/` 中维护；`.claude/skills/` 是 sync 生成的转发入口，不要手改。

## 单一数据源

- 只手写 `plugins/<name>/.codex-plugin/plugin.json`、`plugins/<name>/.codex-mcp.json`（有 MCP 时）与可选的根目录 `plugin-kit.json`。
- 以下内容由 `python scripts/plugin_kit.py sync` 生成，禁止手改：
  - `plugins/<name>/.claude-plugin/plugin.json`（Claude Code）
  - `plugins/<name>/.codebuddy-plugin/plugin.json`（WorkBuddy）
  - 本地开发市场：`.agents/plugins/marketplace.json`、`.claude-plugin/marketplace.json`、`.codebuddy-plugin/marketplace.json`
  - `.claude/skills/`
  - README 的「## 安装」章节
- 版本号只用 `plugin_kit.py bump` 修改。

## 三端兼容

- 三端只共享 `skills/`。插件根目录不放 `.mcp.json`、`mcp/*.json` 和 Codex 格式的 `hooks/hooks.json`，因为 Claude Code 与 WorkBuddy 会自动加载这些默认路径，WorkBuddy 还会让它们覆盖清单里的同名 MCP server。
- MCP server 不依赖工作目录；stdout 只写协议消息，日志写 stderr；工具默认只读，修改数据的工具需要确认。
- MCP 的 `command` 不要按名字启动解释器（`python`、`python3`、`py`），Claude Code 侧也不要依赖 `node`，因为各平台、各客户端的 PATH 不同。应改用编译型启动器，或按平台选择解释器的启动器，见 plugin-create 的 `references/mcp.md`「跨平台启动」。
- Skill 正文引用 MCP 工具时只写短名。
- WorkBuddy 已通过 CLI 校验和宿主规则回放，但桌面端会话尚未完整验收，文档中如实标注。

## 版本与发布

- 采用 SemVer，tag 为 `vX.Y.Z`。CHANGELOG 使用 `## [Unreleased]` 与 `## [X.Y.Z] - YYYY-MM-DD`，只记录使用者能感知的变化。
- 提交信息使用 Conventional Commits。
- commit、push、tag、Release 与 s-plugins 通知都需要用户明确授权。发布计划由用户一次性确认，计划变化需重新确认。只推送到 `origin`，不移动、不覆盖已有 tag 和 Release。

## 文档与验证

- 文档使用简体中文；技术术语、代码标识符和专有名词保留原文。
- 修改后运行 `python scripts/plugin_kit.py sync`、`python scripts/plugin_kit.py check` 与 `python -m unittest discover -s tests`；装有 Claude Code 或 CodeBuddy CLI 时，再分别运行 `claude plugin validate --strict plugins/<name>` 或 `codebuddy plugin validate plugins/<name>`。
- 不提交凭据、Token、内部地址或本机绝对路径；密钥只通过 GitHub Secrets 或环境变量提供。
