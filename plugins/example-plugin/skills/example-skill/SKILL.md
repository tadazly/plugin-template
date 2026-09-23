---
name: example-skill
description: 示例技能：说明本插件模板的目录结构与三端清单的关系。仅在用户明确要求演示示例插件或示例技能时使用；不用于任何实际业务任务。
---

# 示例技能

演示一个三端（Codex、Claude Code、WorkBuddy）通用的 Skill。制作真实插件时删除本目录，按 `plugin-create` 技能编写自己的 Skill。

## 流程

1. 读取插件根目录下的 `.codex-plugin/plugin.json`，说明插件名称、版本与展示信息。
2. 列出 `skills/` 下的全部 Skill，逐一给出一句话用途。
3. 说明 `.claude-plugin/plugin.json` 由 `scripts/plugin_kit.py sync` 生成，Claude Code 与 WorkBuddy 共用。

## 约定

- 调用 MCP 工具时只写工具短名，不写带客户端前缀的全名。
- 长篇资料放在 `references/`，在正文中按需链接。
