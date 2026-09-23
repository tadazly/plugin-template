# Skill 编写规则

目录 `plugins/<name>/skills/<skill>/`：

- `SKILL.md`：必需。
- `agents/openai.yaml`：可选，Codex 中的展示信息。
- `references/`：可选，按需阅读的长资料。
- `scripts/`：可选，Skill 调用的小脚本，优先 Python 标准库，保证 Windows 与 macOS 都能运行。

## Front matter

只用三端共同支持的字段：

```yaml
---
name: <与目录名相同的 kebab-case，≤64 字符>
description: <做什么 + 何时使用（用户会怎么说）+ 不用于什么，≤1024 字>
---
```

- description 决定自动触发，写清触发场景与排除场景。
- Claude Code 专属字段可以写在 front matter，其他客户端会忽略。例如用 `allowed-tools` 预授权只读 MCP 工具，名称形如 `mcp__plugin_<plugin>_<server>__<tool>`。
- 正文里不要出现 `mcp__` 前缀，`check` 会拒绝。

## 正文

- 开头一句话说明用途，然后是 `## 流程`（编号步骤）与 `## 规则`（或 `## 回答要求`）。
- 引用 MCP 工具只写短名（如 `drag_search`）；各客户端给工具加的前缀不同。
- 超过约 200 行的内容拆到 `references/`，正文中用相对链接并说明何时阅读。
- 需要报告结果时使用 PASS / FAIL / BLOCKED / NOT TESTED。
- 不写版本号、本机路径和内部地址。

## agents/openai.yaml

```yaml
interface:
  display_name: "中文展示名"
  short_description: "一句话说明"
  default_prompt: "使用 $<skill> ……"
policy:
  allow_implicit_invocation: true
```

只应在用户明确要求时运行的 Skill，把 `allow_implicit_invocation` 设为 `false`。
