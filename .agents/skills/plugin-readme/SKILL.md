---
name: plugin-readme
description: 按统一规则生成或改写插件仓库的 README.md：插件初始化后把模板说明替换成插件 README，或在功能、配置、工具变化后同步更新。用户要求“写 README”“更新文档”，或 plugin-create、plugin-release 需要更新 README 时使用；不用于 CHANGELOG 与开发文档。
---

# 插件 README

README 首先面向插件使用者，其次面向开发者。使用简体中文，技术术语与代码标识符保留原文。

## 流程

1. 只根据事实写已实现的能力：
   - `plugins/<name>/.codex-plugin/plugin.json`：展示名、说明、`defaultPrompt`、许可证。
   - `plugins/<name>/skills/*/SKILL.md`：Skill 列表与用途。
   - MCP：`.codex-mcp.json` 与 server 源码中的工具名，以及每个工具是否修改数据。
   - 前置条件、环境变量与数据目录（来自源码与 Skill）。
2. 按 [references/readme-template.md](references/readme-template.md) 的章节顺序撰写；README 仍是模板说明（首行为 `# Plugin Template`）时整体替换。
3. `## 安装` 章节只保留标题，正文由 `python scripts/plugin_kit.py sync` 生成，不要手改。
4. 运行 `python scripts/plugin_kit.py sync` 与 `python scripts/plugin_kit.py check`，确认没有 README 相关的警告。

## 规则

- 不写版本号与发布日期（由 CHANGELOG 记录）；不写本机路径、内部地址或 Token。
- 示例提示词与 manifest `defaultPrompt` 一致，或是它的超集。
- 平台支持如实标注，未实测的客户端写“尚未验收”。
- 工具表只写工具短名；会修改数据的工具标注“需确认”。
- 保持精炼：每节先给结论或命令，不重复 manifest 中的长描述。
- 开发细节链接到 `docs/development.md`，不要复制进 README。
