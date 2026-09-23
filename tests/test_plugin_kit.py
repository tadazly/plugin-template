from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import plugin_kit as kit  # noqa: E402

TEMPLATE_ENTRIES = ("plugins", ".agents", "CHANGELOG.md", "README.md", "LICENSE")
WEBSITE = "https://github.com/octo/sample-plugin"


class KitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for entry in TEMPLATE_ENTRIES:
            source = ROOT / entry
            if source.is_dir():
                shutil.copytree(source, self.root / entry)
            else:
                shutil.copy2(source, self.root / entry)
        kit.sync(self.root)

    def init_plugin(self, **overrides: object) -> Path:
        values: dict[str, object] = {
            "name": "sample-plugin",
            "display_name": "示例工具",
            "description": "用于测试的插件",
            "website": WEBSITE,
        }
        values.update(overrides)
        return kit.init(self.root, **values)  # type: ignore[arg-type]

    def finish_plugin(self) -> Path:
        """Initialize and replace every template placeholder, as plugin-create would."""
        plugin = self.init_plugin(short_description="一句话", long_description="完整说明")
        manifest_path = plugin / kit.CODEX_MANIFEST
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["interface"]["defaultPrompt"] = ["用示例工具做一件事。"]
        kit.write_text(manifest_path, kit.dump_json(manifest))
        shutil.rmtree(plugin / "skills" / kit.TEMPLATE_SKILL)
        skill = plugin / "skills" / "do-thing" / "SKILL.md"
        kit.write_text(skill, "---\nname: do-thing\ndescription: 做一件事。\n---\n\n# 做一件事\n")
        kit.write_text(self.root / "README.md", "# 示例工具\n\n## 安装\n\n## 使用\n\n说明。\n")
        kit.write_text(
            self.root / "CHANGELOG.md",
            "# 更新日志\n\n## [Unreleased]\n\n### 新增\n\n- 首个版本。\n",
        )
        kit.sync(self.root)
        return plugin

    def write_mcp(self, plugin: Path, servers: dict[str, object]) -> None:
        kit.write_text(plugin / ".codex-mcp.json", kit.dump_json({"mcpServers": servers}))
        manifest_path = plugin / kit.CODEX_MANIFEST
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["mcpServers"] = kit.CODEX_MCP
        kit.write_text(manifest_path, kit.dump_json(manifest))


class TemplateTests(KitTestCase):
    def test_template_state_passes_check_but_cannot_be_released(self) -> None:
        self.assertEqual([], kit.check(self.root).errors)
        errors = kit.check(self.root, tag="v0.1.0").errors
        self.assertTrue(any("template placeholder" in error for error in errors))
        with self.assertRaises(kit.KitError):
            kit.build_payload(self.root, "v0.1.0")

    def test_repository_template_is_current(self) -> None:
        report = kit.check(ROOT)
        self.assertEqual([], report.errors, report.errors)


class InitTests(KitTestCase):
    def test_init_renames_plugin_and_generates_every_client_file(self) -> None:
        plugin = self.init_plugin()
        self.assertEqual(self.root / "plugins" / "sample-plugin", plugin)
        self.assertFalse((self.root / "plugins" / kit.TEMPLATE_PLUGIN).exists())

        manifest = json.loads((plugin / kit.CODEX_MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual("0.1.0", manifest["version"])
        self.assertEqual(f"{WEBSITE}.git", manifest["repository"])
        self.assertEqual(WEBSITE, manifest["interface"]["websiteURL"])

        claude = json.loads((plugin / kit.CLAUDE_MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual("示例工具", claude["displayName"])
        self.assertEqual(WEBSITE, claude["homepage"])
        self.assertNotIn("interface", claude)

        for relative in (".agents/plugins", ".claude-plugin", ".codebuddy-plugin"):
            marketplace = json.loads((self.root / relative / "marketplace.json").read_text(encoding="utf-8"))
            self.assertEqual("sample-plugin-dev", marketplace["name"])
        self.assertTrue((self.root / ".claude/skills/plugin-create/SKILL.md").is_file())
        self.assertIn("## [Unreleased]", (self.root / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_placeholders_warn_during_development_and_block_release(self) -> None:
        self.init_plugin()
        report = kit.check(self.root)
        self.assertEqual([], report.errors)
        self.assertTrue(any(kit.PLACEHOLDER in warning for warning in report.warnings))
        release = kit.check(self.root, tag="v0.1.0")
        self.assertTrue(any(kit.PLACEHOLDER in error for error in release.errors))
        self.assertTrue(any(kit.TEMPLATE_SKILL in error for error in release.errors))
        self.assertTrue(any("template guide" in error for error in release.errors))

    def test_init_requires_website_without_origin(self) -> None:
        with self.assertRaisesRegex(kit.KitError, "--website"):
            self.init_plugin(website=None)


class McpTests(KitTestCase):
    def test_codex_servers_convert_to_claude_inline_servers(self) -> None:
        converted = kit.convert_mcp_servers(
            {
                "tool": {
                    "command": "./bin/tool",
                    "args": ["mcp", "./config/default.json"],
                    "env": {"TOOL_HOME": "./data"},
                    "cwd": ".",
                    "enabled": True,
                    "default_tools_approval_mode": "approve",
                    "tools": {"write": {"approval_mode": "prompt"}},
                    "tool_timeout_sec": 300,
                },
                "script": {"command": "python", "args": ["./server/main.py"]},
                "off": {"command": "./bin/off", "enabled": False},
            }
        )
        self.assertEqual(
            {
                "tool": {
                    "command": "${CLAUDE_PLUGIN_ROOT}/bin/tool",
                    "args": ["mcp", "${CLAUDE_PLUGIN_ROOT}/config/default.json"],
                    "env": {"TOOL_HOME": "${CLAUDE_PLUGIN_ROOT}/data"},
                },
                "script": {"command": "python", "args": ["${CLAUDE_PLUGIN_ROOT}/server/main.py"]},
            },
            converted,
        )
        with self.assertRaises(kit.KitError):
            kit.convert_mcp_servers({"remote": {"url": "https://example.com/mcp"}})

    def test_check_rejects_root_mcp_json_and_session_relative_paths(self) -> None:
        plugin = self.finish_plugin()
        self.write_mcp(plugin, {"tool": {"command": "node", "args": ["scripts/start.js"]}})
        kit.write_text(plugin / ".mcp.json", "{}\n")
        kit.sync(self.root)
        errors = kit.check(self.root).errors
        self.assertTrue(any(".mcp.json is auto-loaded" in error for error in errors))
        self.assertTrue(any("must start with './'" in error for error in errors))

    def test_missing_binaries_block_only_releases(self) -> None:
        plugin = self.finish_plugin()
        self.write_mcp(plugin, {"tool": {"command": "./bin/tool", "args": ["mcp"]}})
        kit.sync(self.root)
        self.assertEqual([], kit.check(self.root).errors)
        self.assertTrue(any("bin/tool" in error for error in kit.check(self.root, tag="v0.1.0").errors))
        kit.write_text(plugin / "bin" / "tool", "binary")
        kit.write_text(plugin / "bin" / "tool.exe", "binary")
        self.assertFalse(any("bin/tool" in error for error in kit.check(self.root, tag="v0.1.0").errors))

    def use_claude_launcher(self, plugin: Path) -> Path:
        """Codex keeps a Node launcher; Claude Code gets a sh + .cmd launcher pair."""
        self.write_mcp(plugin, {"tool": {"command": "node", "args": ["./scripts/start.js"]}})
        override = {"command": "${CLAUDE_PLUGIN_ROOT}/bin/tool-mcp", "args": []}
        kit.write_text(self.root / kit.KIT_CONFIG, kit.dump_json({"claude": {"mcpServers": {"tool": override}}}))
        kit.sync(self.root)
        (plugin / "bin").mkdir()
        (plugin / "bin" / "tool-mcp").write_bytes(b'#!/bin/sh\nexec python3 "$@"\n')
        (plugin / "bin" / "tool-mcp.cmd").write_bytes(b"@echo off\r\npython %*\r\n")
        return plugin / "bin"

    def test_interpreter_names_are_rejected_and_node_warns_for_claude(self) -> None:
        plugin = self.finish_plugin()
        self.write_mcp(
            plugin,
            {
                "py": {"command": "python3", "args": ["./server/main.py"]},
                "js": {"command": "node", "args": ["./scripts/start.js"]},
                "own": {"command": "./bin/python", "args": ["./server/main.py"]},
            },
        )
        kit.sync(self.root)
        report = kit.check(self.root)
        self.assertEqual(1, sum("starts the interpreter" in error for error in report.errors), report.errors)
        self.assertTrue(any("'py'" in error and "'python3'" in error for error in report.errors))
        self.assertTrue(any("'js'" in warning and "runs 'node'" in warning for warning in report.warnings))

        kit.write_text(self.root / kit.KIT_CONFIG, kit.dump_json({"claude": {"mcpServers": {"own": {"command": "py"}}}}))
        kit.sync(self.root)
        errors = kit.check(self.root).errors
        self.assertTrue(any("plugin-kit.json" in error and "'py'" in error for error in errors), errors)

    def test_claude_launcher_pair_passes_and_reports_platform_gaps(self) -> None:
        bin_dir = self.use_claude_launcher(self.finish_plugin())
        report = kit.check(self.root)
        self.assertEqual([], report.errors)
        self.assertFalse(any("tool-mcp" in warning or "'node'" in warning for warning in report.warnings))
        (bin_dir / "tool-mcp.cmd").unlink()
        self.assertTrue(any("tool-mcp.cmd is missing" in warning for warning in kit.check(self.root).warnings))

    def test_launcher_line_endings_and_encoding(self) -> None:
        bin_dir = self.use_claude_launcher(self.finish_plugin())
        (bin_dir / "tool-mcp").write_bytes(b'#!/bin/sh\r\nexec python3 "$@"\r\n')
        (bin_dir / "tool-mcp.cmd").write_bytes("@echo off\r\necho 缺少 Python\r\n".encode("utf-8"))
        errors = kit.check(self.root).errors
        self.assertTrue(any("CRLF" in error for error in errors), errors)
        self.assertTrue(any("must be ASCII" in error for error in errors), errors)

    def test_tracked_launcher_needs_executable_bit(self) -> None:
        self.use_claude_launcher(self.finish_plugin())
        if kit.git(self.root, "init", "-q") is None:
            self.skipTest("git is not available")
        launcher = "plugins/sample-plugin/bin/tool-mcp"
        kit.git(self.root, "add", "--", launcher)
        kit.git(self.root, "update-index", "--chmod=-x", "--", launcher)
        self.assertTrue(any("executable bit" in error for error in kit.check(self.root).errors))
        kit.git(self.root, "update-index", "--chmod=+x", "--", launcher)
        self.assertFalse(any("executable bit" in error for error in kit.check(self.root).errors))


class ReleaseTests(KitTestCase):
    def test_first_release_then_minor_bump(self) -> None:
        plugin = self.finish_plugin()
        self.assertTrue(any("## [0.1.0]" in error for error in kit.check(self.root, tag="v0.1.0").errors))
        self.assertEqual("0.1.0", kit.bump(self.root, "0.1.0", date="2026-01-01"))
        self.assertEqual([], kit.check(self.root, tag="v0.1.0").errors)
        self.assertEqual("### 新增\n\n- 首个版本。\n", kit.release_notes(self.root))

        with self.assertRaisesRegex(kit.KitError, "empty"):
            kit.bump(self.root, "minor")
        changelog = self.root / "CHANGELOG.md"
        text = changelog.read_text(encoding="utf-8")
        kit.write_text(changelog, text.replace("## [Unreleased]\n", "## [Unreleased]\n\n### 修复\n\n- 修复问题。\n", 1))
        self.assertEqual("0.2.0", kit.bump(self.root, "minor", date="2026-02-01"))
        claude = json.loads((plugin / kit.CLAUDE_MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual("0.2.0", claude["version"])
        self.assertIn("## [0.2.0] - 2026-02-01", changelog.read_text(encoding="utf-8"))
        self.assertTrue(any("tag" in error for error in kit.check(self.root, tag="v0.1.0").errors))

    def test_payload_matches_s_plugins_contract(self) -> None:
        self.finish_plugin()
        payload = kit.build_payload(self.root, "v0.1.0")
        self.assertEqual("plugin-released", payload["event_type"])
        client = payload["client_payload"]
        self.assertEqual(
            {"url": f"{WEBSITE}.git", "path": "./plugins/sample-plugin", "ref": "v0.1.0"},
            client["source"],
        )
        self.assertEqual(set(kit.DISPLAY_FIELDS), set(client["interface"]))
        with self.assertRaisesRegex(kit.KitError, "must equal"):
            kit.build_payload(self.root, "v9.9.9")

    def test_conventional_commits_suggest_bump_level(self) -> None:
        self.assertEqual("patch", kit.conventional_level(["fix: a", "docs: b"], "1.2.3"))
        self.assertEqual("minor", kit.conventional_level(["feat(ui): a"], "1.2.3"))
        self.assertEqual("major", kit.conventional_level(["feat!: drop tool"], "1.2.3"))
        self.assertEqual("minor", kit.conventional_level(["refactor!: rename"], "0.4.0"))


class GeneratedFileTests(KitTestCase):
    def test_readme_install_section_is_generated(self) -> None:
        self.finish_plugin()
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertIn("claude plugin install sample-plugin@s-plugins", readme)
        self.assertIn("codex plugin add sample-plugin@s-plugins", readme)
        self.assertIn("## 使用", readme)
        kit.write_text(self.root / "README.md", readme.replace("s-plugins", "other", 1))
        self.assertTrue(any("stale" in error for error in kit.check(self.root).errors))

    def test_skill_stubs_copy_front_matter_and_prune_stale_files(self) -> None:
        stub = (self.root / ".claude/skills/plugin-release/SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(stub.startswith("---\nname: plugin-release\n"))
        self.assertIn(".agents/skills/plugin-release/SKILL.md", stub)
        stale = self.root / ".claude/skills/removed/SKILL.md"
        kit.write_text(stale, "stale")
        self.assertTrue(any("stale" in error for error in kit.check(self.root).errors))
        kit.sync(self.root)
        self.assertFalse(stale.exists())

    def test_skill_body_must_not_use_client_specific_tool_names(self) -> None:
        plugin = self.finish_plugin()
        skill = plugin / "skills" / "do-thing" / "SKILL.md"
        front = "---\nname: do-thing\ndescription: 做一件事。\nallowed-tools: mcp__plugin_x_y__read\n---\n"
        kit.write_text(skill, front + "\n调用 `read` 工具。\n")
        self.assertEqual([], kit.check(self.root).errors)
        kit.write_text(skill, front + "\n调用 `mcp__plugin_x_y__read`。\n")
        self.assertTrue(any("short name" in error for error in kit.check(self.root).errors))


class SensitiveDataTests(KitTestCase):
    def test_credentials_local_paths_and_forbidden_words_are_rejected(self) -> None:
        token = "gh" + "p_" + "a" * 36
        local_path = "C:" + "\\Users\\someone\\project"
        kit.write_text(self.root / "notes.md", f"token {token}\npath {local_path}\ninternal.example\n")
        with mock.patch.dict(os.environ, {kit.FORBIDDEN_ENV: "Internal.Example"}):
            errors = kit.check(self.root).errors
        self.assertTrue(any("possible credential" in error for error in errors))
        self.assertTrue(any("local absolute path" in error for error in errors))
        self.assertTrue(any("forbidden word #1" in error for error in errors))
        self.assertFalse(any("internal.example" in error.lower() for error in errors))


if __name__ == "__main__":
    unittest.main()
