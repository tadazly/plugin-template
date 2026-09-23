# 编译型插件的发布

插件需要在多个平台构建二进制（Go、Rust 等）时，二进制不提交到 main，只在发布时构建，并放进 tag 对应的提交。可参考 [design-rag](https://github.com/tadazly/design-rag) 的 `.github/workflows/release.yml`。

## 改造 release.yml

1. 触发方式改为 `workflow_dispatch`，输入 `version`（不带 v）与 `source_sha`（40 位）。
2. **preflight job**：`source_sha` 等于 `origin/main`；manifest 版本等于输入版本；同名 tag 与 Release 都不存在；该 SHA 的 CI 成功；`python scripts/plugin_kit.py check` 通过。
3. **build job**：在 `windows-latest`、`macos-15` 等原生 runner 上构建，用隔离的数据目录做真实 MCP 冒烟测试，再上传 artifact。
4. **publish job**：
   - 检出 `source_sha`，下载各平台产物放进 `plugins/<name>/bin/`（如 `<tool>` 与 `<tool>.exe`；非 Windows 平台设置可执行权限）。
   - 运行 `python scripts/plugin_kit.py check --tag vX.Y.Z`，此时会校验二进制是否齐全。
   - 以 noreply 身份提交 `chore(release): assemble vX.Y.Z plugin distribution`（二进制用 `git add -f`）。该提交的父提交是 `source_sha`，不合并回 main。
   - `git tag -a vX.Y.Z -m "<displayName> vX.Y.Z"`，只推送 tag。
   - `gh release create vX.Y.Z --verify-tag --notes-file <notes>`。
5. **notify-s-plugins job** 不变，但 ref 用 `v${{ inputs.version }}`，不要用 `github.ref_name`（它在 `workflow_dispatch` 下是分支名）。

## 配套调整

- 在 `.gitignore` 中忽略 `plugins/<name>/bin/`，防止误把二进制提交到 main；main 上的 `check` 只会对缺失的二进制给出警告。
- 二进制内置版本信息（如 `<tool> --version --json`），发布时核对它与 manifest 一致。
- 第三方依赖的许可证收集到 `plugins/<name>/THIRD_PARTY_NOTICES/`。
- plugin-release 流程的第 4–5 步改为：推送 main，等 CI 通过后运行 `gh workflow run release.yml -f version=X.Y.Z -f source_sha=<sha>`。
