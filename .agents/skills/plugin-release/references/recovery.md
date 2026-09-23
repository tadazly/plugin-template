# 发布故障处理

| 状态 | 处理 |
| --- | --- |
| preflight 有 blockers | 按提示修复后重跑，不要跳过 |
| release 提交已推送，CI 失败 | 修复后追加提交，重新运行 `check --tag`，CI 通过后再打 tag |
| tag 已推送，Release workflow 校验失败 | 不移动 tag。修复问题后发布下一个 patch 版本 |
| GitHub Release 已创建，`notify-s-plugins` 失败（Secret 缺失或过期） | 配置 Secret 后在 Actions 中对该 run 执行 Re-run failed jobs |
| s-plugins 的 update-marketplace 失败 | 查看日志中的 payload 校验错误；修复 manifest 后发布新的 patch 版本 |
| 发布了错误内容 | 发布修复版本；不删除、不覆盖已发布的 tag |

删除 tag 或 Release 必须由用户明确要求并亲自确认。
