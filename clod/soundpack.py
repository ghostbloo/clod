"""Unified sound pack format and converters.

This module defines helpers to load a unified sound pack JSON and convert/apply
it to Claude Code settings hooks. The same sound pack is also consumed by the
Opencode plugin in `.opencode/plugin/sfx.ts`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import json

from .sfx import SoundEffectsManager


SoundEntry = str | dict[str, Any]


def _normalize_path(base_dir: str, entry: SoundEntry) -> str:
    """Resolve a "SoundEntry" to a path string, joining with base_dir if needed."""
    raw = entry if isinstance(entry, str) else str(entry.get("path", ""))
    if not raw:
        return ""
    if raw.startswith("/") or raw.startswith("~"):
        return raw
    base = base_dir.rstrip("/")
    return f"{base}/{raw}"


def _load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        with path.open() as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        return None
    return None


def load_soundpack_from_paths(paths: Iterable[Path]) -> dict[str, Any] | None:
    """Load a sound pack from the first existing path in order."""
    for p in paths:
        data = _load_json_file(p)
        if data is not None:
            return data
    return None


def generate_claude_hooks(pack: dict[str, Any]) -> dict[str, Any]:
    """Generate a Claude Code `hooks` object from a sound pack.

    The pack format supports:
      - baseDir: default "~/.claude/sounds"
      - claude: { [hookType]: { [matcher]: SoundEntry } }
    """
    base_dir = str(pack.get("baseDir") or "~/.claude/sounds")
    claude_cfg = pack.get("claude") or {}

    hooks: dict[str, list[dict[str, Any]]] = {}

    for hook_type, matchers in claude_cfg.items():
        if not isinstance(matchers, dict):
            continue

        matcher_entries: list[dict[str, Any]] = []

        # Group by matcher, generate a single command hook per matcher
        for matcher, entry in matchers.items():
            full_path = _normalize_path(base_dir, entry)
            if not full_path:
                continue

            # Quote when spaces present
            quoted = f'"{full_path}"' if " " in full_path else full_path

            matcher_entries.append(
                {
                    "matcher": matcher,
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"afplay {quoted} &",
                        }
                    ],
                }
            )

        if matcher_entries:
            hooks[hook_type] = matcher_entries

    return hooks


def apply_pack_to_claude_settings(pack: dict[str, Any]) -> dict[str, list[str]]:
    """Apply the pack to the actual Claude settings.json using manager APIs.

    Returns a summary with keys: "applied" and "failed", each listing
    "HookType|Matcher -> filename" entries.
    """
    manager = SoundEffectsManager()
    base_dir = str(pack.get("baseDir") or "~/.claude/sounds")
    claude_cfg = pack.get("claude") or {}

    applied: list[str] = []
    failed: list[str] = []

    for hook_type, matchers in claude_cfg.items():
        if not isinstance(matchers, dict):
            continue
        for matcher, entry in matchers.items():
            full_path = _normalize_path(base_dir, entry)
            filename = Path(full_path).name
            if manager.set_sound_mapping(hook_type, matcher, filename):
                applied.append(f"{hook_type}|{matcher} -> {filename}")
            else:
                failed.append(f"{hook_type}|{matcher} -> {filename}")

    return {"applied": applied, "failed": failed}


