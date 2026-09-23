# 开发与发布

## 环境

- Python 3.9+：`scripts/plugin_kit.py` 只依赖标准库。
- 本地试装：Claude Code 或 Codex CLI。
- 发布：已登录的 GitHub CLI `gh`。

## 初始化

用模板创建仓库后运行一次，通常由 agent 按 plugin-create 技能执行：

```bash
python scripts/plugin_kit.py init --name my-plugin --display-name "我的插件" --description "一句话说明"
```

init 会做这些事：

- 重命名 `plugins/example-plugin/`。
- 写入 manifest：版本 `0.1.0`，`repository` 与 `websiteURL` 取自 `origin`。
- 清空 CHANGELOG，然后运行 sync。

之后替换 `TODO` 占位，删除示例 Skill。

## 日常开发

修改 manifest、Skill 或 MCP 配置后运行：

```bash
python scripts/plugin_kit.py sync
python scripts/plugin_kit.py check
python -m unittest discover -s tests
claude plugin validate --strict plugins/<name>
```

push main 或提 PR 时，CI（`.github/workflows/ci.yml`）会在 Ubuntu 与 Windows 上运行同样的检查，并用 Claude Code CLI 校验清单。

`check` 会检查以下内容：

- manifest 字段与长度限制。
- MCP 路径写法，以及二进制是否成对。
- Skill 的 front matter。
- 生成文件是否最新。
- CHANGELOG 格式。
- 疑似凭据与本机绝对路径。

带 `--tag vX.Y.Z` 时进入发布模式：残留的 `TODO`、示例 Skill、模板 README 与缺失的二进制都会从警告变为错误。

## 本地调试

| 客户端 | 方式 |
| --- | --- |
| Claude Code | `claude --plugin-dir ./plugins/<name>`；或 `claude plugin marketplace add .` 后 `claude plugin install <name>@<name>-dev` |
| Codex | `codex plugin marketplace add .` 后 `codex plugin add <name>@<name>-dev`，然后新建会话 |
| WorkBuddy | 尚未验收 |

- 本地开发市场名为 `<name>-dev`。它安装的是工作区内容，与 s-plugins 上的正式版本互不影响。
- MCP 变更需要新开会话才生效。`claude mcp list` 可做健康检查，但会真实启动 server；有状态的 server 先把数据目录指向临时目录。

## 发布配置

发布后由 `release.yml` 的 `notify-s-plugins` job 通知 s-plugins，每个仓库配置一次：

1. 创建 fine-grained personal access token：Repository access 选 Only select repositories → `tadazly/s-plugins`；权限为 Contents: Read and write。
2. 运行 `gh secret set S_PLUGINS_DISPATCH_TOKEN --repo <owner>/<repo>`，按提示粘贴 Token。
3. 可选：Secret `PLUGIN_KIT_FORBIDDEN` 设为逗号分隔的内部词，CI 会拒绝包含它们的文件。

详见 `.agents/skills/plugin-release/references/s-plugins-setup.md`。

## 发布

对 agent 说“发布新版本”，由 plugin-release 技能执行：

```text
preflight → 你确认计划 → bump → 提交并推送 main → CI 通过
→ 推送 tag vX.Y.Z → release.yml 校验并创建 GitHub Release → 通知 s-plugins
```

手动发布时按 `.agents/skills/plugin-release/SKILL.md` 的步骤执行。需要构建多平台二进制的插件，参考同目录下的 `references/compiled-release.md` 改造 `release.yml`。

## 同步模板更新

```bash
git remote add template https://github.com/tadazly/plugin-template.git   # 仅首次
git fetch template
git checkout template/main -- scripts/plugin_kit.py tests/test_plugin_kit.py .agents/skills .github/workflows docs/development.md
python scripts/plugin_kit.py sync
python scripts/plugin_kit.py check
```

检查 diff 后再提交。插件自己的 README、CHANGELOG 与 AGENTS.md 中的定制内容要手工合并，不要直接覆盖。
