# README 模板

按以下顺序撰写，尖括号内替换为实际内容；没有内容的可选章节整节删除。

````markdown
# <displayName>

<shortDescription>。<一两句补充：解决什么问题、适合谁用>

## 功能

- <按使用者价值列出 3–6 条>

## 安装

## 使用

安装后直接用自然语言描述需求，例如：

- <defaultPrompt 1>
- <defaultPrompt 2>

| Skill | 用途 |
| --- | --- |
| `<skill>` | <一句话> |

| MCP 工具 | 用途 | 读写 |
| --- | --- | --- |
| `<tool>` | <一句话> | 只读 / 需确认 |

## 配置

<可选：前置条件（如 Python 3.9+）、环境变量、数据目录>

## 平台支持

| 客户端 | 状态 |
| --- | --- |
| Codex | 已验收 / 尚未验收 |
| Claude Code | 已验收 / 尚未验收 |
| WorkBuddy | 已验收 / 尚未验收 |

## 开发

```bash
python scripts/plugin_kit.py sync    # 生成各端清单
python scripts/plugin_kit.py check   # 校验（CI 同样执行）
python -m unittest discover -s tests
```

本地调试、发布配置与模板更新见 [docs/development.md](docs/development.md)，版本变化见 [CHANGELOG.md](CHANGELOG.md)。

## 许可

<许可证名称>，见 [LICENSE](LICENSE)。
````

- 没有 MCP 工具时删除工具表；只有一个 Skill 时可省略 Skill 表。
- `## 安装` 下面留空，`sync` 会填入三端安装命令。
