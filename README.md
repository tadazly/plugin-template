# Plugin Template

Codex、Claude Code、WorkBuddy 三端通用的 Agent 插件模板。模板内置 agent 规则与技能、清单生成与校验脚本，以及发布到 [S Plugins](https://github.com/tadazly/s-plugins) 市场的 CI/CD。

> 本文件是模板说明。插件制作完成后，agent 会按 `plugin-readme` 技能把它改写成插件自己的 README；开发说明保留在 [docs/development.md](docs/development.md)。

## 快速开始

1. 用模板创建仓库并克隆：

   ```bash
   gh repo create <owner>/<repo> --public --template tadazly/plugin-template --clone
   ```

   也可以在 GitHub 页面点击 **Use this template**。

2. 初次配置（只需一次）：
   - 本机安装 Python 3.9+；需要本地试装时，再安装 Claude Code 或 Codex CLI。
   - 在 GitHub 仓库的 Actions Secrets 中添加 `S_PLUGINS_DISPATCH_TOKEN`，发布后才能自动登记到 s-plugins。步骤见[发布配置](docs/development.md#发布配置)。

3. 在仓库根目录打开 Codex 或 Claude Code，描述需求：

   ```text
   用 plugin-create 技能做一个插件：<插件做什么、给谁用、需要哪些能力>
   ```

   agent 会运行 `init` 重命名插件，实现 Skill 或 MCP，生成三端清单并校验，最后用 `plugin-readme` 改写本 README。

4. 发布：对 agent 说“发布新版本”。agent 先做只读预检，你确认计划后，它提交代码并推送 tag。CI 随后创建 GitHub Release 并通知 s-plugins，三个客户端的市场会一起更新。

## 仓库结构

```text
plugins/<name>/                  可分发的插件（init 前为 example-plugin）
  .codex-plugin/plugin.json      唯一数据源（Codex manifest）
  .claude-plugin/plugin.json     生成：Claude Code 与 WorkBuddy 共用
  .codex-mcp.json                可选：Codex MCP 配置
  skills/<skill>/SKILL.md        三端共用的 Skill
.agents/skills/                  agent 开发技能：plugin-create、plugin-readme、plugin-release
.claude/skills/                  生成：Claude Code 的技能转发入口
.agents/plugins/、.claude-plugin/、.codebuddy-plugin/
                                 生成：本地开发市场
scripts/plugin_kit.py            init / sync / check / bump / preflight / payload
.github/workflows/               CI 与发布
AGENTS.md、CLAUDE.md             agent 规则（CLAUDE.md 引用 AGENTS.md）
docs/development.md              开发、调试与发布说明
```

## 常用命令

```bash
python scripts/plugin_kit.py sync        # 重新生成各端清单与转发入口
python scripts/plugin_kit.py check       # 校验（CI 同样执行）
python scripts/plugin_kit.py preflight   # 发布前只读预检
python -m unittest discover -s tests
```

## 参考插件

- [design-rag](https://github.com/tadazly/design-rag)：Go 二进制 MCP，发布时构建多平台二进制。
- [egret-agent-inspector](https://github.com/tadazly/egret-agent-inspector)：Python MCP 加浏览器扩展，包含多个 Skill。
