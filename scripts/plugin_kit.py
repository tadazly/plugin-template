#!/usr/bin/env python3
"""plugin-kit: keep a Codex / Claude Code / WorkBuddy plugin repository consistent.

The Codex manifest ``plugins/<name>/.codex-plugin/plugin.json`` is the single
source of truth. ``sync`` regenerates every derived file, ``check`` validates the
repository (CI runs it on every push and tag), and the release helpers bump the
version, extract release notes and build the s-plugins dispatch payload.

Standard library only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Marketplace that receives releases (see README "发布配置").
MARKETPLACE_REPOSITORY = "tadazly/s-plugins"
MARKETPLACE_NAME = "s-plugins"

TEMPLATE_PLUGIN = "example-plugin"
TEMPLATE_SKILL = "example-skill"
TEMPLATE_README_TITLE = "# Plugin Template"
PLACEHOLDER = "TODO"

CODEX_MANIFEST = Path(".codex-plugin/plugin.json")
CLAUDE_MANIFEST = Path(".claude-plugin/plugin.json")
CODEX_MCP = "./.codex-mcp.json"
CLAUDE_PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"
DEV_SKILLS = Path(".agents/skills")
CLAUDE_SKILLS = Path(".claude/skills")
KIT_CONFIG = Path("plugin-kit.json")
CHANGELOG = Path("CHANGELOG.md")
README = Path("README.md")
INSTALL_HEADING = "## 安装"
UNRELEASED_HEADING = "## [Unreleased]"

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
VERSION_HEADING_RE = re.compile(r"^## \[(?P<version>[^\]]+)\](?P<rest>.*)$", re.M)
BIN_REFERENCE_RE = re.compile(r"^\./bin/([^/\\]+?)(?:\.exe)?$")
ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")
SECRET_RES = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
)
# Split literals keep this file from matching its own patterns.
LOCAL_PATH_RE = re.compile(
    r"(?i)\b[a-z]:(?:\\\\|\\|/)users(?:\\\\|\\|/)[^\\/\s\"']+"
    + "|/" + r"Users/[^/\s\"']+/"
    + "|/" + r"home/[^/\s\"']+/"
)
INTERFACE_LIMITS = {
    "displayName": 80,
    "shortDescription": 240,
    "longDescription": 1000,
    "developerName": 80,
}
DISPLAY_FIELDS = ("displayName", "shortDescription", "longDescription", "developerName", "websiteURL")
# Comma-separated words that must never appear in the public repository (for
# example internal domains). CI injects them from a secret so the list itself
# stays private; matches are reported without echoing the word.
FORBIDDEN_ENV = "PLUGIN_KIT_FORBIDDEN"
SKILL_STUB_BODY = (
    "本技能正文位于 `.agents/skills/{name}/SKILL.md`（Codex 与 Claude Code 共用）。"
    "先完整阅读并遵循该文件；其中的相对路径以 `.agents/skills/{name}/` 为基准。\n"
)


class KitError(Exception):
    """A problem the user must fix; reported without a traceback."""


# ---------------------------------------------------------------- helpers


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise KitError(f"missing file: {path.as_posix()}") from error
    except json.JSONDecodeError as error:
        raise KitError(f"invalid JSON in {path.as_posix()}: {error}") from error


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def same_content(current: bytes, expected: bytes) -> bool:
    return current.replace(b"\r\n", b"\n") == expected.replace(b"\r\n", b"\n")


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_https_url(value: Any) -> bool:
    return non_empty(value) and re.fullmatch(r"https://[^\s<>\"'`]+", value) is not None


def plugin_dir(root: Path) -> Path:
    manifests = sorted((root / "plugins").glob("*/.codex-plugin/plugin.json"))
    if len(manifests) != 1:
        raise KitError(
            f"expected exactly one plugins/<name>/.codex-plugin/plugin.json, found {len(manifests)}"
        )
    return manifests[0].parents[1]


def read_manifest(root: Path) -> tuple[Path, dict[str, Any]]:
    plugin = plugin_dir(root)
    manifest = load_json(plugin / CODEX_MANIFEST)
    if not isinstance(manifest, dict):
        raise KitError(f"{relative(root, plugin / CODEX_MANIFEST)} must contain a JSON object")
    return plugin, manifest


def kit_config(root: Path) -> dict[str, Any]:
    path = root / KIT_CONFIG
    if not path.is_file():
        return {}
    config = load_json(path)
    if not isinstance(config, dict):
        raise KitError(f"{KIT_CONFIG.as_posix()} must contain a JSON object")
    return config


def section_re(heading: str) -> re.Pattern[str]:
    return re.compile(rf"(?ms)^{re.escape(heading)}[^\n]*\n.*?(?=^## |\Z)")


def replace_section(text: str, heading: str, section: str) -> str | None:
    """Replace the level-2 section starting with ``heading``; None if absent."""
    matches = list(section_re(heading).finditer(text))
    if not matches:
        return None
    if len(matches) > 1:
        raise KitError(f"README.md must contain at most one '{heading}' section")
    match = matches[0]
    tail = "\n" if match.end() == len(text) else "\n\n"
    return text[: match.start()] + section.rstrip() + tail + text[match.end() :]


def github_url(remote: str) -> str | None:
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
        r"(?P<slug>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?",
        remote.strip(),
    )
    return f"https://github.com/{match.group('slug')}" if match else None


def origin_url(root: Path) -> str | None:
    remote = git(root, "remote", "get-url", "origin")
    return github_url(remote) if remote else None


FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)


def frontmatter(text: str) -> dict[str, str] | None:
    """Parse the top-level ``key: value`` lines of a SKILL.md YAML front matter."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() and not key.startswith((" ", "\t", "-")):
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


# ------------------------------------------------------------- rendering


def to_claude_path(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("./"):
        return f"{CLAUDE_PLUGIN_ROOT}/{value[2:]}"
    return value


def load_codex_mcp(plugin: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    declared = manifest.get("mcpServers")
    if declared is None:
        return {}
    if declared != CODEX_MCP:
        raise KitError(f"mcpServers must be {CODEX_MCP!r} so Claude Code does not auto-load it")
    config = load_json(plugin / CODEX_MCP)
    servers = config.get("mcpServers") if isinstance(config, dict) else None
    if not isinstance(servers, dict):
        raise KitError(f"{CODEX_MCP} must contain an mcpServers object")
    return servers


def convert_mcp_servers(servers: dict[str, Any]) -> dict[str, Any]:
    """Codex stdio servers -> Claude Code / WorkBuddy inline servers.

    Codex resolves ``./`` paths against the plugin root (``cwd: "."``); Claude
    Code ignores ``cwd`` and runs servers in the user's session directory, so
    plugin paths are rewritten to ``${CLAUDE_PLUGIN_ROOT}``. Codex-only fields
    (approval modes, timeouts, cwd, enabled) are dropped.
    """
    converted: dict[str, Any] = {}
    for name, server in servers.items():
        if not isinstance(server, dict) or server.get("enabled", True) is False:
            continue
        command = server.get("command")
        if not non_empty(command):
            raise KitError(
                f"MCP server {name!r}: only stdio servers with a command are converted; "
                f"declare other servers under 'claude' in {KIT_CONFIG.as_posix()}"
            )
        entry: dict[str, Any] = {"command": to_claude_path(command)}
        if server.get("args"):
            entry["args"] = [to_claude_path(arg) for arg in server["args"]]
        if server.get("env"):
            entry["env"] = {key: to_claude_path(value) for key, value in server["env"].items()}
        converted[name] = entry
    return converted


def deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def render_claude_manifest(root: Path, plugin: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Claude Code manifest; WorkBuddy reads the same .claude-plugin directory."""
    interface = manifest.get("interface") or {}
    claude = {
        "name": manifest.get("name"),
        "displayName": interface.get("displayName"),
        "version": manifest.get("version"),
        "description": manifest.get("description"),
        "author": manifest.get("author"),
        "homepage": interface.get("websiteURL"),
        "repository": manifest.get("repository"),
        "license": manifest.get("license"),
        "keywords": manifest.get("keywords"),
        "mcpServers": convert_mcp_servers(load_codex_mcp(plugin, manifest)),
    }
    claude = {key: value for key, value in claude.items() if value not in (None, "", [], {})}
    return deep_merge(claude, kit_config(root).get("claude", {}))


def render_dev_marketplaces(manifest: dict[str, Any]) -> dict[Path, dict[str, Any]]:
    """Local marketplaces for installing the working tree in each client."""
    name = manifest.get("name")
    interface = manifest.get("interface") or {}
    display = interface.get("displayName") or name
    marketplace = f"{name}-dev"
    source = f"./plugins/{name}"
    description = f"{display} 本地开发市场"
    owner = {"name": interface.get("developerName") or (manifest.get("author") or {}).get("name")}
    common = {
        "name": name,
        "version": manifest.get("version"),
        "description": manifest.get("description"),
    }
    return {
        Path(".agents/plugins/marketplace.json"): {
            "name": marketplace,
            "interface": {"displayName": f"{display} (dev)"},
            "plugins": [
                {
                    **common,
                    "source": {"source": "local", "path": source},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": interface.get("category"),
                    "interface": {key: interface[key] for key in DISPLAY_FIELDS if key in interface},
                }
            ],
        },
        Path(".claude-plugin/marketplace.json"): {
            "name": marketplace,
            "owner": owner,
            "metadata": {"description": description},
            "plugins": [{**common, "displayName": display, "source": source}],
        },
        Path(".codebuddy-plugin/marketplace.json"): {
            "name": marketplace,
            "owner": owner,
            "description": description,
            "plugins": [{**common, "source": source}],
        },
    }


def render_install_section(manifest: dict[str, Any]) -> str:
    name = manifest.get("name")
    display = (manifest.get("interface") or {}).get("displayName") or name
    return "\n".join(
        [
            INSTALL_HEADING,
            "",
            f"通过 [S Plugins](https://github.com/{MARKETPLACE_REPOSITORY}) 插件市场安装，安装后新建会话生效。",
            "",
            "Claude Code：",
            "",
            "```bash",
            f"claude plugin marketplace add {MARKETPLACE_REPOSITORY}",
            f"claude plugin install {name}@{MARKETPLACE_NAME}",
            "```",
            "",
            "Codex：",
            "",
            "```bash",
            f"codex plugin marketplace add {MARKETPLACE_REPOSITORY}",
            f"codex plugin add {name}@{MARKETPLACE_NAME}",
            "```",
            "",
            f"WorkBuddy（尚未验收）：在插件市场中添加 Git 市场 "
            f"`https://github.com/{MARKETPLACE_REPOSITORY}.git`，然后安装 **{display}**。",
        ]
    )


def render_skill_stubs(root: Path) -> dict[Path, bytes]:
    """Claude Code only reads .claude/skills; Codex reads .agents/skills.

    Each stub copies the front matter (so Claude can trigger the skill) and
    points at the single shared body in .agents/skills.
    """
    source = root / DEV_SKILLS
    stubs: dict[Path, bytes] = {}
    if not source.is_dir():
        return stubs
    for skill in sorted(path for path in source.iterdir() if (path / "SKILL.md").is_file()):
        match = FRONTMATTER_RE.match((skill / "SKILL.md").read_text(encoding="utf-8"))
        if match is None:
            raise KitError(f"{(DEV_SKILLS / skill.name / 'SKILL.md').as_posix()}: missing YAML front matter")
        text = f"---\n{match.group(1)}\n---\n\n{SKILL_STUB_BODY.format(name=skill.name)}"
        stubs[root / CLAUDE_SKILLS / skill.name / "SKILL.md"] = text.encode("utf-8")
    return stubs


def render_outputs(root: Path) -> dict[Path, bytes]:
    plugin, manifest = read_manifest(root)
    outputs = {
        plugin / CLAUDE_MANIFEST: dump_json(render_claude_manifest(root, plugin, manifest)).encode("utf-8")
    }
    for path, marketplace in render_dev_marketplaces(manifest).items():
        outputs[root / path] = dump_json(marketplace).encode("utf-8")
    readme_path = root / README
    if readme_path.is_file():
        readme = readme_path.read_text(encoding="utf-8")
        updated = replace_section(readme, INSTALL_HEADING, render_install_section(manifest))
        if updated is not None:
            outputs[readme_path] = updated.encode("utf-8")
    outputs.update(render_skill_stubs(root))
    return outputs


def stale_mirror_files(root: Path, outputs: dict[Path, bytes]) -> list[Path]:
    mirror = root / CLAUDE_SKILLS
    if not mirror.is_dir():
        return []
    return [path for path in sorted(mirror.rglob("*")) if path.is_file() and path not in outputs]


# ------------------------------------------------------------- commands


def sync(root: Path) -> list[str]:
    """Regenerate derived files; returns the repository-relative paths that changed."""
    outputs = render_outputs(root)
    changed: list[str] = []
    for path, content in outputs.items():
        if path.is_file() and same_content(path.read_bytes(), content):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        changed.append(relative(root, path))
    for path in stale_mirror_files(root, outputs):
        path.unlink()
        changed.append(f"{relative(root, path)} (removed)")
    mirror = root / CLAUDE_SKILLS
    if mirror.is_dir():
        for directory in sorted((p for p in mirror.rglob("*") if p.is_dir()), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
    return changed


class Report:
    def __init__(self, release: bool) -> None:
        self.release = release
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def release_blocker(self, message: str) -> None:
        (self.errors if self.release else self.warnings).append(message)


def check_manifest(report: Report, root: Path, plugin: Path, manifest: dict[str, Any]) -> None:
    label = relative(root, plugin / CODEX_MANIFEST)
    name = manifest.get("name")
    if name != plugin.name or not isinstance(name, str) or NAME_RE.fullmatch(name) is None:
        report.error(f"{label}: name must be the kebab-case directory name {plugin.name!r}")
    version = manifest.get("version")
    if not isinstance(version, str) or SEMVER_RE.fullmatch(version) is None:
        report.error(f"{label}: version must use strict semver (no 'v' prefix)")
    description = manifest.get("description")
    if not non_empty(description) or len(description) > 500:
        report.error(f"{label}: description must contain 1 to 500 characters")
    if not non_empty((manifest.get("author") or {}).get("name")):
        report.error(f"{label}: author.name is required")

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        report.error(f"{label}: interface must be an object")
        interface = {}
    for field, limit in INTERFACE_LIMITS.items():
        value = interface.get(field)
        if not non_empty(value) or len(value) > limit:
            report.error(f"{label}: interface.{field} must contain 1 to {limit} characters")
    if not non_empty(interface.get("category")):
        report.error(f"{label}: interface.category is required")
    if not is_https_url(interface.get("websiteURL")):
        report.error(f"{label}: interface.websiteURL must be an https URL")
    for field in ("capabilities", "defaultPrompt"):
        values = interface.get(field)
        if not isinstance(values, list) or not values or not all(non_empty(v) for v in values):
            report.error(f"{label}: interface.{field} must be a non-empty array of strings")
    prompts = interface.get("defaultPrompt")
    if isinstance(prompts, list) and (len(prompts) > 3 or any(len(str(p)) > 128 for p in prompts)):
        report.error(f"{label}: interface.defaultPrompt allows 1 to 3 prompts of at most 128 characters")
    repository = manifest.get("repository")
    if not (is_https_url(repository) and str(repository).endswith(".git")):
        report.error(f"{label}: repository must be the https clone URL ending with .git")

    has_skills = (plugin / "skills").is_dir()
    if has_skills and manifest.get("skills") != "./skills/":
        report.error(f"{label}: declare \"skills\": \"./skills/\" (Codex only loads declared skills)")
    if not has_skills and "skills" in manifest:
        report.error(f"{label}: skills is declared but plugins/{plugin.name}/skills/ does not exist")
    if (plugin / ".mcp.json").exists():
        report.error(
            f"plugins/{plugin.name}/.mcp.json is auto-loaded by Claude Code and WorkBuddy; "
            f"move the Codex MCP config to {CODEX_MCP}"
        )
    if (plugin / CODEX_MCP).exists() and manifest.get("mcpServers") != CODEX_MCP:
        report.error(f"{label}: declare \"mcpServers\": \"{CODEX_MCP}\"")

    placeholders = [key for key, value in flatten(manifest) if PLACEHOLDER in str(value)]
    if placeholders:
        report.release_blocker(f"{label}: replace {PLACEHOLDER} placeholders in {', '.join(placeholders)}")


def flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        items: list[tuple[str, Any]] = []
        for key, child in value.items():
            items.extend(flatten(child, f"{prefix}.{key}" if prefix else key))
        return items
    if isinstance(value, list):
        return [item for index, child in enumerate(value) for item in flatten(child, f"{prefix}[{index}]")]
    return [(prefix, value)]


def check_mcp(report: Report, root: Path, plugin: Path, manifest: dict[str, Any]) -> None:
    try:
        servers = load_codex_mcp(plugin, manifest)
        convert_mcp_servers(servers)
    except KitError as error:
        report.error(str(error))
        return
    label = relative(root, plugin / CODEX_MCP)
    tools: set[str] = set()
    for name, server in servers.items():
        values = [server.get("command"), *(server.get("args") or []), *(server.get("env") or {}).values()]
        for value in (v for v in values if isinstance(v, str)):
            if ABSOLUTE_PATH_RE.match(value):
                report.error(f"{label}: server {name!r} uses an absolute path {value!r}")
            elif ("/" in value or "\\" in value) and not value.startswith(("./", "-", "${", "http")):
                report.error(
                    f"{label}: server {name!r} path {value!r} must start with './' "
                    "(relative paths resolve against the user's session directory in Claude Code)"
                )
            match = BIN_REFERENCE_RE.match(value)
            if match:
                tools.add(match.group(1))
        if server.get("cwd") not in (None, "."):
            report.warn(f"{label}: server {name!r} cwd is ignored by Claude Code; do not depend on it")
    # Compiled plugins may keep binaries out of main and add them only to the
    # release tag, so a missing binary blocks releases but not development.
    for tool in sorted(tools):
        present = [f for f in (tool, f"{tool}.exe") if (plugin / "bin" / f).is_file()]
        if not present:
            report.release_blocker(f"plugins/{plugin.name}/bin/{tool} (or {tool}.exe) is referenced but missing")
        elif len(present) == 1:
            report.warn(f"plugins/{plugin.name}/bin/ only ships {present[0]}; the other platform cannot start it")


def check_skills(report: Report, root: Path, skills_root: Path, plugin_skills: bool) -> None:
    if not skills_root.is_dir():
        return
    for directory in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        skill_file = directory / "SKILL.md"
        label = relative(root, skill_file)
        if not skill_file.is_file():
            report.error(f"{relative(root, directory)}: missing SKILL.md")
            continue
        text = skill_file.read_text(encoding="utf-8")
        fields = frontmatter(text)
        if fields is None:
            report.error(f"{label}: missing YAML front matter")
            continue
        name = fields.get("name", "")
        if name != directory.name or NAME_RE.fullmatch(name) is None or len(name) > 64:
            report.error(f"{label}: name must equal the kebab-case directory name (max 64 characters)")
        description = fields.get("description", "")
        if not description or len(description) > 1024:
            report.error(f"{label}: description must contain 1 to 1024 characters")
        body = FRONTMATTER_RE.sub("", text, count=1)
        if plugin_skills and "mcp__" in body:
            report.error(
                f"{label}: refer to MCP tools by their short name in the body; 'mcp__' prefixes "
                "differ between clients (Claude-only allowed-tools belong in the front matter)"
            )
        if plugin_skills and PLACEHOLDER in text:
            report.release_blocker(f"{label}: replace {PLACEHOLDER} placeholders")


def check_generated(report: Report, root: Path) -> None:
    try:
        outputs = render_outputs(root)
    except KitError as error:
        report.error(str(error))
        return
    stale = [
        relative(root, path)
        for path, content in outputs.items()
        if not path.is_file() or not same_content(path.read_bytes(), content)
    ]
    stale += [relative(root, path) for path in stale_mirror_files(root, outputs)]
    if stale:
        report.error(f"generated files are stale, run 'python scripts/plugin_kit.py sync': {', '.join(stale)}")


def changelog_sections(text: str) -> dict[str, str]:
    headings = list(VERSION_HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        next_level_two = re.search(r"^## ", body, re.M)
        sections[heading.group("version")] = (body[: next_level_two.start()] if next_level_two else body).strip()
    return sections


def check_changelog(report: Report, root: Path, version: Any, tag: str | None) -> None:
    path = root / CHANGELOG
    if not path.is_file():
        report.error("CHANGELOG.md is missing")
        return
    sections = changelog_sections(path.read_text(encoding="utf-8"))
    if "Unreleased" not in sections:
        report.error(f"CHANGELOG.md must keep a '{UNRELEASED_HEADING}' section")
    for heading in sections:
        if heading != "Unreleased" and SEMVER_RE.fullmatch(heading) is None:
            report.error(f"CHANGELOG.md: '## [{heading}]' is not a semver version")
    if tag is None:
        return
    if tag != f"v{version}":
        report.error(f"tag {tag!r} must equal 'v' + manifest version ({version!r})")
    if not sections.get(str(version)):
        report.error(f"CHANGELOG.md needs a non-empty '## [{version}] - YYYY-MM-DD' section")


def check_template_state(report: Report, root: Path, plugin: Path, version: Any) -> None:
    if plugin.name == TEMPLATE_PLUGIN:
        if report.release:
            report.error("the template placeholder plugin cannot be released; run 'plugin_kit.py init' first")
        return
    if (plugin / "skills" / TEMPLATE_SKILL).exists():
        report.release_blocker(f"replace or remove plugins/{plugin.name}/skills/{TEMPLATE_SKILL}")
    readme = root / README
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    if text.startswith(TEMPLATE_README_TITLE):
        report.release_blocker("README.md is still the template guide; rewrite it with the plugin-readme skill")
    elif not section_re(INSTALL_HEADING).search(text):
        report.release_blocker(f"README.md needs a '{INSTALL_HEADING}' section (filled by sync)")
    if isinstance(version, str) and re.search(rf"(?<![\d.]){re.escape(version)}(?![\d.])", text):
        report.release_blocker("README.md must not mention the plugin version; CHANGELOG.md tracks versions")


def tracked_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        names = [name for name in result.stdout.decode("utf-8").split("\0") if name]
        return [root / name for name in names if (root / name).is_file()]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts]


def check_sensitive(report: Report, root: Path) -> None:
    forbidden = [w.strip().lower() for w in os.environ.get(FORBIDDEN_ENV, "").split(",") if w.strip()]
    for path in tracked_files(root):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > 2_000_000 or b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8", errors="ignore")
        for number, line in enumerate(text.splitlines(), start=1):
            where = f"{relative(root, path)}:{number}"
            if any(pattern.search(line) for pattern in SECRET_RES):
                report.error(f"{where}: possible credential; use GitHub Secrets instead")
            if LOCAL_PATH_RE.search(line):
                report.error(f"{where}: local absolute path; keep machine paths out of the repo")
            lowered = line.lower()
            for index, word in enumerate(forbidden, start=1):
                if word in lowered:
                    report.error(f"{where}: forbidden word #{index} from {FORBIDDEN_ENV}")


def check(root: Path, tag: str | None = None) -> Report:
    report = Report(release=tag is not None)
    try:
        plugin, manifest = read_manifest(root)
    except KitError as error:
        report.error(str(error))
        return report
    check_manifest(report, root, plugin, manifest)
    check_mcp(report, root, plugin, manifest)
    check_skills(report, root, plugin / "skills", plugin_skills=True)
    check_skills(report, root, root / DEV_SKILLS, plugin_skills=False)
    check_generated(report, root)
    check_changelog(report, root, manifest.get("version"), tag)
    check_template_state(report, root, plugin, manifest.get("version"))
    check_sensitive(report, root)
    return report


def next_version(current: str, level: str) -> str:
    if SEMVER_RE.fullmatch(level):
        return level
    core = re.match(r"^(\d+)\.(\d+)\.(\d+)", current)
    if core is None:
        raise KitError(f"current version {current!r} is not semver")
    major, minor, patch = (int(part) for part in core.groups())
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise KitError("level must be major, minor, patch or an explicit semver version")


def promote_unreleased(text: str, version: str, date: str) -> str:
    match = section_re(UNRELEASED_HEADING).search(text)
    if match is None:
        raise KitError(f"CHANGELOG.md needs a '{UNRELEASED_HEADING}' section")
    body = match.group(0).split("\n", 1)[1].strip() if "\n" in match.group(0) else ""
    if not body:
        raise KitError("CHANGELOG.md Unreleased section is empty; describe the changes first")
    if version in changelog_sections(text):
        raise KitError(f"CHANGELOG.md already contains version {version}")
    section = f"{UNRELEASED_HEADING}\n\n## [{version}] - {date}\n\n{body}\n"
    tail = "\n" if match.end() == len(text) else "\n\n"
    return text[: match.start()] + section.rstrip() + tail + text[match.end() :]


def bump(root: Path, level: str, date: str | None = None) -> str:
    """Set the release version and promote CHANGELOG Unreleased.

    Passing the current version explicitly releases it as is (the first 0.1.0).
    """
    plugin, manifest = read_manifest(root)
    if plugin.name == TEMPLATE_PLUGIN:
        raise KitError("run 'plugin_kit.py init' before releasing")
    current = str(manifest.get("version"))
    version = next_version(current, level)
    changelog_path = root / CHANGELOG
    changelog = promote_unreleased(
        changelog_path.read_text(encoding="utf-8"), version, date or dt.date.today().isoformat()
    )
    manifest["version"] = version
    write_text(plugin / CODEX_MANIFEST, dump_json(manifest))
    write_text(changelog_path, changelog)
    sync(root)
    return version


def release_notes(root: Path, version: str | None = None) -> str:
    _, manifest = read_manifest(root)
    version = version or str(manifest.get("version"))
    notes = changelog_sections((root / CHANGELOG).read_text(encoding="utf-8")).get(version)
    if not notes:
        raise KitError(f"CHANGELOG.md has no notes for {version}")
    return notes + "\n"


def build_payload(root: Path, ref: str) -> dict[str, Any]:
    """plugin-released repository_dispatch payload for s-plugins.

    Always sends the full display metadata so the marketplace follows the
    manifest; source.url and source.path must stay stable across releases.
    """
    plugin, manifest = read_manifest(root)
    if plugin.name == TEMPLATE_PLUGIN:
        raise KitError("the template placeholder plugin cannot be published")
    if ref != f"v{manifest.get('version')}":
        raise KitError(f"ref {ref!r} must equal 'v' + manifest version ({manifest.get('version')!r})")
    interface = manifest.get("interface") or {}
    return {
        "event_type": "plugin-released",
        "client_payload": {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "description": manifest.get("description"),
            "source": {
                "url": manifest.get("repository"),
                "path": f"./plugins/{plugin.name}",
                "ref": ref,
            },
            "interface": {key: interface.get(key) for key in DISPLAY_FIELDS},
        },
    }


def conventional_level(subjects: list[str], current: str) -> str:
    """Suggest a bump level from Conventional Commit subjects since the last tag."""
    if any(re.match(r"^\w+(\([^)]*\))?!:", s) or "BREAKING CHANGE" in s for s in subjects):
        return "minor" if current.startswith("0.") else "major"
    if any(re.match(r"^feat(\([^)]*\))?:", s) for s in subjects):
        return "minor"
    return "patch"


def preflight(root: Path) -> dict[str, Any]:
    """Read-only release readiness report (run 'git fetch --prune --tags' first)."""
    plugin, manifest = read_manifest(root)
    current = str(manifest.get("version"))
    blockers: list[str] = []
    warnings: list[str] = []
    if plugin.name == TEMPLATE_PLUGIN:
        blockers.append("run 'plugin_kit.py init' first")
    if git(root, "rev-parse", "--abbrev-ref", "HEAD") != "main":
        blockers.append("releases are cut from the main branch")
    if git(root, "status", "--porcelain"):
        blockers.append("working tree is not clean")
    counts = git(root, "rev-list", "--left-right", "--count", "origin/main...HEAD")
    if counts is None:
        warnings.append("origin/main is unknown; fetch first")
    elif counts.split()[0] != "0":
        blockers.append("main is behind origin/main; pull first")
    email = git(root, "config", "user.email") or ""
    if not email.endswith("@users.noreply.github.com"):
        warnings.append("git user.email is not a GitHub noreply address")
    tags = [t for t in (git(root, "tag", "--list", "v*", "--sort=-v:refname") or "").splitlines() if t]
    last_tag = tags[0] if tags else None
    log_range = [f"{last_tag}..HEAD"] if last_tag else ["HEAD"]
    subjects = [s for s in (git(root, "log", "--format=%s", *log_range) or "").splitlines() if s]
    level = conventional_level(subjects, current)
    if last_tag == f"v{current}":
        suggested = next_version(current, level)
    else:
        # First release, or the manifest is already ahead of the last tag.
        suggested = current
        if last_tag:
            warnings.append(f"manifest version {current} is not the last tag {last_tag}; releasing it as is")
    if f"v{suggested}" in tags:
        blockers.append(f"tag v{suggested} already exists")
    unreleased = changelog_sections((root / CHANGELOG).read_text(encoding="utf-8")).get("Unreleased")
    if not unreleased:
        blockers.append("CHANGELOG.md Unreleased section is empty")
    report = check(root)
    blockers += report.errors
    return {
        "plugin": manifest.get("name"),
        "currentVersion": current,
        "lastTag": last_tag,
        "commitsSinceLastTag": subjects,
        "suggestedLevel": level if last_tag else "initial",
        "suggestedVersion": suggested,
        "blockers": blockers,
        "warnings": warnings + report.warnings,
    }


def init(
    root: Path,
    *,
    name: str,
    display_name: str,
    description: str,
    short_description: str | None = None,
    long_description: str | None = None,
    developer: str = "tadazly",
    category: str = "Productivity",
    website: str | None = None,
    license_id: str | None = None,
    keywords: list[str] | None = None,
) -> Path:
    template = root / "plugins" / TEMPLATE_PLUGIN
    if not template.is_dir():
        raise KitError("already initialized: plugins/example-plugin does not exist")
    if NAME_RE.fullmatch(name) is None or name == TEMPLATE_PLUGIN:
        raise KitError("--name must be lowercase kebab-case and differ from the template name")
    website = website or origin_url(root)
    if not is_https_url(website):
        raise KitError("pass --website or add the GitHub remote 'origin' first")

    manifest = load_json(template / CODEX_MANIFEST)
    manifest.update(
        {
            "name": name,
            "version": "0.1.0",
            "description": description,
            "author": {"name": developer},
            "repository": f"{website}.git",
            "keywords": keywords or [],
        }
    )
    if license_id:
        manifest["license"] = license_id
    manifest["interface"].update(
        {
            "displayName": display_name,
            "shortDescription": short_description or f"{PLACEHOLDER}: 一句话说明插件用途",
            "longDescription": long_description or f"{PLACEHOLDER}: 完整说明插件能力、适用场景与前置条件",
            "developerName": developer,
            "category": category,
            "websiteURL": website,
            "defaultPrompt": [f"{PLACEHOLDER}: 写 1-3 条典型提示词"],
        }
    )
    target = root / "plugins" / name
    template.rename(target)
    write_text(target / CODEX_MANIFEST, dump_json(manifest))
    changelog = root / CHANGELOG
    header = changelog.read_text(encoding="utf-8").split(UNRELEASED_HEADING, 1)[0].rstrip()
    write_text(changelog, f"{header}\n\n{UNRELEASED_HEADING}\n")
    sync(root)
    return target


# ------------------------------------------------------------------- CLI


def annotate(level: str, message: str) -> str:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return f"::{level}::{message}"
    return f"{level}: {message}"


def main(argv: list[str] | None = None) -> int:
    # Payloads and release notes are piped to gh or files: always UTF-8 with LF,
    # also on Windows where the console code page may differ.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="turn the template into a named plugin")
    init_parser.add_argument("--name", required=True, help="kebab-case plugin id")
    init_parser.add_argument("--display-name", required=True)
    init_parser.add_argument("--description", required=True, help="one sentence, max 500 characters")
    init_parser.add_argument("--short-description")
    init_parser.add_argument("--long-description")
    init_parser.add_argument("--developer", default="tadazly")
    init_parser.add_argument("--category", default="Productivity")
    init_parser.add_argument("--website", help="defaults to the GitHub URL of remote 'origin'")
    init_parser.add_argument("--license", dest="license_id", help="SPDX id, e.g. MIT or Apache-2.0")
    init_parser.add_argument("--keywords", help="comma-separated keywords")

    commands.add_parser("sync", help="regenerate Claude manifest, dev marketplaces, skill mirror, README install")
    check_parser = commands.add_parser("check", help="validate the repository (CI runs this)")
    check_parser.add_argument("--tag", help="release tag vX.Y.Z; enables release checks")
    bump_parser = commands.add_parser("bump", help="bump the version and promote CHANGELOG Unreleased")
    bump_parser.add_argument("level", help="major, minor, patch or an explicit X.Y.Z")
    notes_parser = commands.add_parser("release-notes", help="print CHANGELOG notes for a version")
    notes_parser.add_argument("version", nargs="?")
    payload_parser = commands.add_parser("payload", help="print the s-plugins plugin-released dispatch JSON")
    payload_parser.add_argument("--ref", required=True, help="release tag vX.Y.Z")
    commands.add_parser("preflight", help="read-only release readiness report (JSON)")
    info_parser = commands.add_parser("info", help="print plugin name, version and directory")
    info_parser.add_argument("--field", choices=["name", "version", "dir", "displayName"])

    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "init":
            keywords = [k.strip() for k in (args.keywords or "").split(",") if k.strip()]
            target = init(
                root,
                name=args.name,
                display_name=args.display_name,
                description=args.description,
                short_description=args.short_description,
                long_description=args.long_description,
                developer=args.developer,
                category=args.category,
                website=args.website,
                license_id=args.license_id,
                keywords=keywords,
            )
            print(f"initialized {relative(root, target)}; replace the {PLACEHOLDER} placeholders next")
        elif args.command == "sync":
            changed = sync(root)
            print("\n".join(f"updated {path}" for path in changed) or "generated files are current")
        elif args.command == "check":
            report = check(root, args.tag)
            for message in report.warnings:
                print(annotate("warning", message))
            for message in report.errors:
                print(annotate("error", message))
            if report.errors:
                print(f"check failed: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
                return 1
            print(f"check passed with {len(report.warnings)} warning(s)")
        elif args.command == "bump":
            print(bump(root, args.level))
        elif args.command == "release-notes":
            sys.stdout.write(release_notes(root, args.version))
        elif args.command == "payload":
            sys.stdout.write(dump_json(build_payload(root, args.ref)))
        elif args.command == "preflight":
            result = preflight(root)
            sys.stdout.write(dump_json(result))
            return 1 if result["blockers"] else 0
        elif args.command == "info":
            plugin, manifest = read_manifest(root)
            details = {
                "name": manifest.get("name"),
                "version": manifest.get("version"),
                "dir": relative(root, plugin),
                "displayName": (manifest.get("interface") or {}).get("displayName"),
            }
            print(details[args.field] if args.field else json.dumps(details, ensure_ascii=False))
    except KitError as error:
        print(annotate("error", str(error)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
