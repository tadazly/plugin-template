---
name: plugin-release
description: 按 SemVer 发布插件新版本：只读预检，确定版本号并整理 CHANGELOG，提交并推送 tag；由 CI 创建 GitHub Release 并通知 s-plugins 插件市场，最后验收市场更新。用户要求“发布”“发版”“出新版本”、首次配置 s-plugins 推送或排查发布失败时使用。
---

# 发布插件

发布链路：`plugin_kit.py bump` → 提交并推送 main → CI 通过 → 推送 tag `vX.Y.Z` → `release.yml` 校验并创建 GitHub Release → `notify-s-plugins` 发送 `plugin-released` → s-plugins 更新 Codex、Claude Code、WorkBuddy 三个市场。

## 授权

用户说“发布”只授权只读预检。预检后把完整计划一次性交给用户确认：版本号、CHANGELOG 摘要、release 提交、推送 main、推送 tag、GitHub Release、s-plugins 通知。计划有任何变化都要重新确认。只推送到 `origin`；不移动、不覆盖已有的 tag 或 Release；出错就发新的 patch 版本。

## 流程

1. **只读预检**：

   ```bash
   git fetch --prune --tags origin
   python scripts/plugin_kit.py preflight
   gh run list --workflow CI --branch main --limit 1
   gh secret list
   ```

   preflight 输出 JSON，包含 `blockers`、`warnings`、`suggestedVersion`，以及上个 tag 以来的提交。`gh secret list` 只用来核对 `S_PLUGINS_DISPATCH_TOKEN` 这个名称是否存在，不读取值；缺失时按 [references/s-plugins-setup.md](references/s-plugins-setup.md) 引导用户配置。有 blockers 就停止并报告。
2. **确定版本**。按下文「版本号规范」判断，参考 `suggestedVersion`，然后向用户确认完整计划。
3. **准备发布**：

   ```bash
   python scripts/plugin_kit.py bump <X.Y.Z>
   python scripts/plugin_kit.py check --tag vX.Y.Z
   python -m unittest discover -s tests
   ```

   bump 会写入版本、把 `[Unreleased]` 的内容移到 `[X.Y.Z] - 日期`，并运行 sync。首次发布传入当前版本（如 `0.1.0`），只整理 CHANGELOG、不改版本号。
4. **提交并推送**：`git add -A`，`git commit -m "chore(release): prepare vX.Y.Z"`，`git push origin main`；用 `gh run watch` 等这个提交的 CI 通过。
5. **打 tag**：`git tag -a vX.Y.Z -m "<displayName> vX.Y.Z"`，`git push origin vX.Y.Z`。
6. **验收**，每一步按 PASS / FAIL / BLOCKED / NOT TESTED 报告：
   - `gh run watch` 等 Release workflow 完成，再用 `gh release view vX.Y.Z` 确认 Release。
   - s-plugins：`gh run list -R tadazly/s-plugins --workflow update-marketplace.yml --limit 1` 显示成功，且 `.agents/plugins/marketplace.json` 中本插件的 `version`、`source.ref` 已更新。
   - 可选实测：`claude plugin marketplace update s-plugins` 后运行 `claude plugin update <name>@s-plugins`。

## 版本号规范

使用 SemVer `MAJOR.MINOR.PATCH`。tag 写成 `vX.Y.Z`，manifest 中不带 `v`。

| 变化 | 级别 |
| --- | --- |
| 删除或改名 Skill、MCP 工具；工具参数或返回值不兼容；需要用户迁移数据 | MAJOR（`0.x` 阶段用 MINOR） |
| 新增 Skill、工具、参数或能力，且向后兼容 | MINOR |
| 修复、性能、文案与提示词调整、文档 | PATCH |

- 首个版本 `0.1.0`，稳定后发 `1.0.0`。
- 提交信息使用 Conventional Commits（`feat:`、`fix:`、`docs:`、`chore:`；不兼容变更用 `feat!:` 或在正文写 `BREAKING CHANGE:`），preflight 据此建议版本级别。
- 版本号只通过 `plugin_kit.py bump` 修改；README 中不写版本号。

## CHANGELOG

```markdown
## [Unreleased]

## [0.2.0] - 2026-01-31

### 新增

- ……
```

分类：新增、变更、修复、移除、升级提示（需要用户重启、重装或迁移时写）。只记录使用者能感知的变化。

## 参考

- 故障处理：[references/recovery.md](references/recovery.md)
- 需要构建二进制的插件：[references/compiled-release.md](references/compiled-release.md)
