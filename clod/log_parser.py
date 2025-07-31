"""Claude Code log parsing utilities."""

import json
from pathlib import Path
from typing import Any

from .models.claude_log import ClaudeLogEntry, ClaudeSession


def parse_jsonl_file(file_path: Path) -> ClaudeSession:
    """Parse a JSONL log file into a ClaudeSession."""
    entries = []
    session_id = None

    with file_path.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                entry = ClaudeLogEntry(**data)
                entries.append(entry)

                if session_id is None and entry.session_id:
                    session_id = entry.session_id

            except Exception as e:
                print(f"Warning: Failed to parse line {line_num}: {e}")
                continue

    if not session_id:
        # Use filename as fallback session ID
        session_id = file_path.stem

    return ClaudeSession(session_id=session_id, entries=entries)


def find_log_files(projects_dir: Path | None = None) -> list[Path]:
    """Find all Claude Code log files."""
    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"

    if not projects_dir.exists():
        return []

    log_files = []
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir():
            for log_file in project_dir.glob("*.jsonl"):
                log_files.append(log_file)

    return sorted(log_files, key=lambda f: f.stat().st_mtime, reverse=True)


def get_recent_sessions(limit: int = 10) -> list[ClaudeSession]:
    """Get the most recent Claude Code sessions."""
    log_files = find_log_files()[:limit]
    sessions = []

    for log_file in log_files:
        try:
            session = parse_jsonl_file(log_file)
            sessions.append(session)
        except Exception as e:
            print(f"Warning: Failed to parse {log_file}: {e}")
            continue

    return sessions


def export_session_to_sdk_format(session: ClaudeSession) -> list[dict[str, Any]]:
    """Export session to claude-code-sdk compatible format."""
    sdk_messages: list[dict[str, Any]] = []

    for entry in session.get_conversation_thread():
        if not entry.message:
            continue

        message_data: dict[str, Any] = {
            "type": entry.type,
            "role": entry.message.role,
            "content": [],
        }

        # Add metadata
        if entry.message.id:
            message_data["id"] = entry.message.id
        if entry.message.model:
            message_data["model"] = entry.message.model
        if entry.message.usage:
            message_data["usage"] = entry.message.usage.dict(exclude_none=True)

        # Handle content
        if isinstance(entry.message.content, str):
            message_data["content"] = [{"type": "text", "text": entry.message.content}]
        elif isinstance(entry.message.content, list):
            content_list: list[dict] = []
            for block in entry.message.content:
                if hasattr(block, "dict"):
                    content_list.append(block.dict(exclude_none=True))
            message_data["content"] = content_list

        sdk_messages.append(message_data)

    return sdk_messages
