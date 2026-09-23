# MCP server 规则

## 配置位置

- Codex：`plugins/<name>/.codex-mcp.json`，manifest 声明 `"mcpServers": "./.codex-mcp.json"`。
- Claude Code 与 WorkBuddy：`sync` 把 Codex 配置转换为 `.claude-plugin/plugin.json` 的内联 `mcpServers`。
- 插件根目录禁止 `.mcp.json`：Claude Code 与 WorkBuddy 会自动加载它，并按用户会话目录解析其中的相对路径。

## Codex 配置模板

```json
{
  "mcpServers": {
    "<server>": {
      "command": "./bin/<tool>",
      "args": ["mcp"],
      "cwd": ".",
      "enabled": true,
      "default_tools_approval_mode": "approve",
      "tools": {
        "<mutating_tool>": { "approval_mode": "prompt" }
      },
      "startup_timeout_sec": 30,
      "tool_timeout_sec": 300
    }
  }
}
```

`sync` 的转换规则：

- `command`、`args`、`env` 中以 `./` 开头的值改写为 `${CLAUDE_PLUGIN_ROOT}/…`；PATH 上的命令（`python`、`node`）保持原样。插件内的路径必须以 `./` 开头，`check` 会拒绝其他写法。
- 丢弃 Codex 专属字段：`cwd`、`enabled`、`default_tools_approval_mode`、`tools`、`*_timeout_sec`。审批策略只在 Codex 生效；Claude Code 侧可在 Skill front matter 用 `allowed-tools` 预授权只读工具。
- `enabled: false` 的 server 不输出。只转换 stdio server；其他类型写在 `plugin-kit.json` 的 `claude.mcpServers`。

## 运行时约定

- stdout 只写 MCP 协议消息，日志写 stderr。
- 不依赖工作目录：Claude Code 以用户会话目录启动 server。路径从脚本自身位置或 `${CLAUDE_PLUGIN_ROOT}` 推导；启动后可切换到用户主目录，避免 Windows 锁住插件缓存目录，导致无法更新或卸载。
- 状态与数据写到用户数据目录（Windows `%APPDATA%` / `%LOCALAPPDATA%`，macOS `~/Library/Application Support`），不写插件目录，因为更新会替换缓存目录。提供环境变量覆盖数据目录，便于隔离测试。
- 工具默认只读。修改用户数据的工具在 Codex 配置中设为 `approval_mode: "prompt"`，并在 Skill 中要求先向用户确认。
- 大结果分页或截断，并告诉调用方如何继续获取。

## 运行时选择

| 方案 | 适用 | 参考 |
| --- | --- | --- |
| 编译二进制（Go 等） | 追求性能、不想依赖运行时 | design-rag：命令 `./bin/drag`，同时提供 `bin/drag`（macOS）与 `bin/drag.exe`（Windows）。Windows 上的 Claude Code 会为无扩展名命令自动选用 `.exe`（已在 Claude Code 2.1.280 实测） |
| Python 标准库脚本 | 逻辑简单、依赖少 | egret-agent-inspector：`python ./server/<server>.py`，要求用户安装 Python 3 |
| Node 脚本 | 需要 Node 生态 | 用户未必装有 Node；用作启动器时先检测运行时版本，并给出清晰的错误提示 |

编译型插件的二进制不提交到 main，由发布流程加进 tag，见 plugin-release 的 [compiled-release.md](../../plugin-release/references/compiled-release.md)。

## 验证

- `python scripts/plugin_kit.py check` 会检查路径写法，以及 `bin/` 中的二进制是否成对。
- `claude mcp list` 做健康检查时会真实启动 server；有状态的 server 先把数据目录指向临时目录。
