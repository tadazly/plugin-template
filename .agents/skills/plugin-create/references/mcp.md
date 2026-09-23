# MCP server 规则

## 配置位置

- Codex：`plugins/<name>/.codex-mcp.json`，manifest 声明 `"mcpServers": "./.codex-mcp.json"`。
- Claude Code 与 WorkBuddy：`sync` 把 Codex 配置转换为 `.claude-plugin/plugin.json` 的内联 `mcpServers`，再深度合并根目录 `plugin-kit.json` 的 `claude` 对象。
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

- `command`、`args`、`env` 中以 `./` 开头的值改写为 `${CLAUDE_PLUGIN_ROOT}/…`，其他值原样保留。插件内的路径必须以 `./` 开头，`check` 会拒绝其他写法。
- 丢弃 Codex 专属字段：`cwd`、`enabled`、`default_tools_approval_mode`、`tools`、`*_timeout_sec`。审批策略只在 Codex 生效；Claude Code 侧可在 Skill front matter 用 `allowed-tools` 预授权只读工具。
- `enabled: false` 的 server 不输出。只转换 stdio server；其他类型写在 `plugin-kit.json` 的 `claude.mcpServers`。
- 两端需要不同的启动方式时，在 `plugin-kit.json` 的 `claude.mcpServers.<server>` 中覆盖 Claude Code 侧的配置。合并时列表会被整体替换，所以要显式写出 `args`，没有参数时写 `[]`：

  ```json
  {
    "claude": {
      "mcpServers": {
        "<server>": { "command": "${CLAUDE_PLUGIN_ROOT}/bin/<launcher>", "args": [] }
      }
    }
  }
  ```

## 运行时约定

- stdout 只写 MCP 协议消息，日志写 stderr。
- 不依赖工作目录：Claude Code 以用户会话目录启动 server。路径从脚本自身位置或 `${CLAUDE_PLUGIN_ROOT}` 推导；启动后可切换到用户主目录，避免 Windows 锁住插件缓存目录，导致无法更新或卸载。
- 状态与数据写到用户数据目录（Windows `%APPDATA%` / `%LOCALAPPDATA%`，macOS `~/Library/Application Support`），不写插件目录，因为更新会替换缓存目录。提供环境变量覆盖数据目录，便于隔离测试。
- 工具默认只读。修改用户数据的工具在 Codex 配置中设为 `approval_mode: "prompt"`，并在 Skill 中要求先向用户确认。
- 大结果分页或截断，并告诉调用方如何继续获取。

## 跨平台启动（易踩坑）

同一个 server 要在 Windows 和 macOS 上、在 Codex 和 Claude Code 里都能启动。以下都是实际踩过的坑：

- **不要按名字启动解释器**：
  - macOS 默认没有 `python`，只有 `python3`。
  - Windows 的 python.org 安装只提供 `python` 和 `py`；`python3` 往往只是 WindowsApps 下的商店占位程序，一运行就失败。
  - egret-agent-inspector 在这里反复出过问题：
    - Codex 配置先把 `python` 改成 `python3`（3.4.2），结果 Windows 又不能用，最后改为 Node 启动器按平台选择（3.5.0）。
    - Claude Code 配置一直写着 `python`，在 macOS 上报 `ENOENT: Executable not found in $PATH`。
  - `check` 会拒绝以 `python`、`python3`、`py` 作为 `command`。
- **各客户端的 PATH 不同**：
  - 同一台 Windows 上，Codex 启动的 MCP 能找到 fnm 安装的 node，Claude Code 会话却找不到。
  - Claude Code 与 WorkBuddy 不自带 Node，所以在 Codex 里能启动不代表在 Claude Code 里也能启动。
  - Claude Code 侧的 `command` 为 `node` 时，`check` 会给出警告。
- **Claude Code 忽略 `cwd`**：server 在用户会话目录启动，插件内的文件一律通过 `${CLAUDE_PLUGIN_ROOT}` 定位。
- **不要在 Git Bash 里验证 Windows**：Git Bash 的 PATH 里有 `sh`，Claude Code 会按 shebang 执行 sh 启动器，结果看起来正常；在普通 PowerShell 里却会连接失败。

两种方案都只写一份 Codex 配置（command 为 `./bin/<name>`，`cwd` 为 `.`），由 `sync` 转换为 Claude Code 的 `${CLAUDE_PLUGIN_ROOT}/bin/<name>`，不需要按客户端分别配置：

| 方案 | 做法 | 验证情况 |
| --- | --- | --- |
| 编译二进制或编译型启动器 | 同时提供 `bin/<tool>`（macOS）和 `bin/<tool>.exe`（Windows） | design-rag 采用这种方式。两个客户端在 Windows 上都会为无扩展名命令选用 `.exe` |
| 解释型 server 的启动器对 | 同时提供 sh 启动器 `bin/<launcher>` 和 `bin/<launcher>.cmd`，由启动器选择解释器 | 两个客户端在 Windows 上都会把无扩展名命令解析到 `.cmd`，交给 cmd.exe 执行，参数经 `%*` 原样传递；macOS 执行 sh 启动器。只提供 sh 启动器时，Windows 无法启动 |

以上结论的实测版本：
- Claude Code 2.1.280：Windows 和 macOS；
- Codex 0.156.1：Windows；
- Codex 0.155.0-alpha.16：macOS，即 ChatGPT 桌面端自带的版本。

Node 启动器（如 egret-agent-inspector 的 `scripts/start_mcp.js`）只在能找到 `node` 的客户端里可用，Claude Code 侧不要依赖它。

启动器约定：

- 按平台依次尝试解释器：Windows 为 `python` → `py -3` → `python3`，macOS/Linux 为 `python3` → `python`。每个候选先确认版本满足要求，这样可以跳过商店占位程序。另外提供 `<PLUGIN>_PYTHON` 环境变量，允许手动指定解释器。
- sh 启动器要有 shebang、使用 LF、带可执行位。Windows 上 `core.filemode=false`，新文件会以 100644 提交，需要运行 `git update-index --chmod=+x plugins/<name>/bin/<launcher>`。
- `.cmd` 只写 ASCII，因为 cmd.exe 按系统代码页读取批处理；换行由 `.gitattributes` 固定为 CRLF。
- 找不到解释器时，向 stderr 写一句说明，并以非零状态退出。

sh 启动器 `bin/<launcher>`：

```sh
#!/bin/sh
server="$(dirname -- "$0")/../server/main.py"
for py in "$EXAMPLE_PYTHON" python3 python; do
  [ -n "$py" ] || continue
  if "$py" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
    exec "$py" "$server" "$@"
  fi
done
echo "example-plugin requires Python 3.8+ (tried python3, python); set EXAMPLE_PYTHON to override" >&2
exit 1
```

Windows 启动器 `bin/<launcher>.cmd`：

```bat
@echo off
setlocal
set "SERVER=%~dp0..\server\main.py"
set "CHECK=import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"
if defined EXAMPLE_PYTHON (
  "%EXAMPLE_PYTHON%" -c "%CHECK%" >nul 2>&1 && (set PY="%EXAMPLE_PYTHON%"& goto run)
)
for %%P in ("python" "py -3" "python3") do (
  %%~P -c "%CHECK%" >nul 2>&1 && (set "PY=%%~P"& goto run)
)
>&2 echo example-plugin requires Python 3.8+ (tried python, py -3, python3); set EXAMPLE_PYTHON to override
exit /b 1
:run
%PY% "%SERVER%" %*
exit /b %ERRORLEVEL%
```

使用时把 `example-plugin`、`EXAMPLE_PYTHON` 和 `server/main.py` 替换成插件自己的名称和路径。这两个启动器已按上文版本在 Claude Code 和 Codex 中实测：
- Windows 上，如果 `python` 只是商店占位程序，会回退到 `py -3`；找不到任何解释器时以 1 退出。
- macOS 上使用 PATH 中的 `python3`。

编译型插件的二进制不提交到 main，由发布流程加进 tag，见 plugin-release 的 [compiled-release.md](../../plugin-release/references/compiled-release.md)。

## 验证

- `python scripts/plugin_kit.py check` 会检查以下内容：
  - 路径写法；
  - 是否按名字启动解释器，以及 Claude Code 侧是否使用 `node`；
  - `bin/` 中的程序是否覆盖两个平台；
  - sh 启动器的换行符和 git 可执行位；
  - `.cmd` 是否只含 ASCII。
- `claude mcp list` 做健康检查时会真实启动 server；有状态的 server 先把数据目录指向临时目录。
- 在 macOS 和 Windows 上分别用隔离配置实测，即把 `CLAUDE_CONFIG_DIR`、`CODEX_HOME` 指向临时目录；Windows 在普通 PowerShell 中测试。
