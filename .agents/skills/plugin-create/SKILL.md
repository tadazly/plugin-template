---
name: plugin-create
description: 在基于 plugin-template 的仓库中，按用户需求制作或修改 Codex、Claude Code、WorkBuddy 三端通用插件：初始化插件，设计并实现 Skill 与 MCP server，生成各端清单并校验。用户要求“做一个插件”“把需求做成插件”“给插件加技能或工具”时使用；发布版本用 plugin-release，改写 README 用 plugin-readme。
---

# 制作插件

把用户需求落成一个三端通用插件：只手写 Codex 清单与 Skill，其余清单由 `scripts/plugin_kit.py sync` 生成。

## 流程

1. **澄清需求**。确认插件解决什么问题、谁在哪些客户端使用；只需 Skill（流程与提示），还是需要 MCP 工具（确定性执行、访问本地资源或大量数据）；运行时依赖（Python、Node、编译二进制）；哪些操作会修改用户数据。信息不足时先问，不要猜。
2. **初始化（仅首次）**。仓库里还有 `plugins/example-plugin/` 时运行：

   ```bash
   python scripts/plugin_kit.py init --name <kebab-name> --display-name "<展示名>" --description "<一句话说明>" \
     [--short-description "<卖点>"] [--long-description "<完整说明>"] [--category Productivity] \
     [--license MIT] [--keywords a,b,c]
   ```

   `--website` 默认取 `origin` 的 GitHub 地址。init 会重命名插件目录、写入 Codex manifest（版本 `0.1.0`）、清空 CHANGELOG 并运行 sync。随后替换全部 `TODO` 占位，删除 `skills/example-skill/`；换许可证时同时替换根目录 `LICENSE`。
3. **设计**。按场景拆成若干 Skill；只有确定性执行、读写本地资源或处理大量数据时才做 MCP 工具，工具默认只读，修改数据的工具单独列出。规则见 [references/skills.md](references/skills.md) 与 [references/mcp.md](references/mcp.md)。
4. **实现**。
   - Skill：`plugins/<name>/skills/<skill>/SKILL.md`，可选 `agents/openai.yaml`、`references/`、`scripts/`。
   - MCP：`plugins/<name>/.codex-mcp.json`，manifest 声明 `"mcpServers": "./.codex-mcp.json"`。启动命令不要直接写 `python`、`python3`、`py` 等解释器名，按 [references/mcp.md](references/mcp.md) 的「跨平台启动」选择方案。
   - 程序源码放仓库根目录（如 `src/`、`server/`），插件目录只放运行所需文件。
   - manifest 字段规则见 [references/manifest.md](references/manifest.md)。
5. **同步与校验**。

   ```bash
   python scripts/plugin_kit.py sync
   python scripts/plugin_kit.py check
   python -m unittest discover -s tests
   claude plugin validate --strict plugins/<name>
   codebuddy plugin validate plugins/<name>
   ```

6. **本地试装**。Claude Code：`claude --plugin-dir ./plugins/<name>`。Codex：`codex plugin marketplace add .` 后 `codex plugin add <name>@<name>-dev`。MCP 改动需新开会话；有状态的 server 先用环境变量把数据目录指向临时目录。
7. **收尾**。在 CHANGELOG `## [Unreleased]` 下按「新增 / 变更 / 修复 / 移除 / 升级提示」记录使用者可感知的变化；用 plugin-readme 更新 README；按 PASS / FAIL / NOT TESTED 报告验证结果。

## 规则

- 只手写 `.codex-plugin/plugin.json`、`.codex-mcp.json` 与可选的根目录 `plugin-kit.json`；`.claude-plugin/plugin.json`、`.codebuddy-plugin/plugin.json`、根目录三个开发市场、`.claude/skills/` 与 README「## 安装」由 sync 生成。
- 插件根目录不放 `.mcp.json`、`mcp/*.json` 与 Codex 格式的 `hooks/hooks.json`：Claude Code 与 WorkBuddy 会自动加载这些默认路径，WorkBuddy 还会让它们覆盖清单里的同名 MCP server。
- 插件名、目录名与 manifest `name` 一致，发布后不改名；`repository` 发布后不改。
- 密钥通过环境变量读取并在 README「配置」说明；不提交凭据、Token、内部地址或本机绝对路径。
- 制作插件只修改工作区；commit、push、tag 需要用户明确授权。
