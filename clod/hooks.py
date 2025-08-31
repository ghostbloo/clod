"""Hook management for Claude Code."""

import json
import subprocess
from pathlib import Path
from typing import Any, ClassVar

import click


class HookManager:
    """Manages Claude Code hooks."""

    SCOPE_PATHS: ClassVar[dict[str, str]] = {
        "user": "~/.claude/settings.json",
        "project": "./.claude/settings.json",
        "local": "./.claude/settings.local.json",
    }

    def __init__(
        self, settings_path: Path | None = None, scope: str | None = None
    ) -> None:
        if scope and scope in self.SCOPE_PATHS:
            self.settings_path = Path(self.SCOPE_PATHS[scope]).expanduser().resolve()
        else:
            self.settings_path = (
                settings_path or Path.home() / ".claude" / "settings.json"
            )
        self.hooks_dir = Path.home() / ".claude" / "hooks"
        self.hooks_dir.mkdir(parents=True, exist_ok=True)

    def _load_settings(self) -> dict[str, Any]:
        """Load Claude Code settings."""
        if not self.settings_path.exists():
            return {"hooks": {}}

        try:
            with self.settings_path.open() as f:
                data: dict[str, Any] = json.load(f)
            return data
        except (OSError, json.JSONDecodeError):
            hooks_dict: dict[str, Any] = {"hooks": {}}
            return hooks_dict

    def _save_settings(self, settings: dict[str, Any]) -> None:
        """Save Claude Code settings."""
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        with self.settings_path.open("w") as f:
            json.dump(settings, f, indent=2)

    def list_hooks(self) -> list[dict[str, Any]]:
        """List all configured hooks."""
        settings = self._load_settings()
        hooks = []

        for event_name, matchers in settings.get("hooks", {}).items():
            for matcher_config in matchers:
                matcher = matcher_config.get("matcher", "*")
                for hook in matcher_config.get("hooks", []):
                    hooks.append(
                        {
                            "event": event_name,
                            "matcher": matcher,
                            "type": hook.get("type", "command"),
                            "command": hook.get("command", ""),
                        }
                    )

        return hooks

    def add_hook(
        self,
        hook_type: str,  # Should be a valid HookEventType value
        matcher: str,
        command: str | None = None,
        script_path: str | None = None,
        template: bool = False,
        name: str | None = None,
    ) -> str:
        """Add a new hook."""
        settings = self._load_settings()
        hooks_config = settings.setdefault("hooks", {})

        # Convert hook type to event name format
        event_name = self._normalize_event_name(hook_type)

        if template:
            # Create cchooks Python template
            if not name:
                event_hooks_count = len(hooks_config.get(event_name, []))
                # Convert PascalCase to snake_case for name
                name_base = "".join(
                    [
                        "_" + c.lower() if c.isupper() and i > 0 else c.lower()
                        for i, c in enumerate(hook_type)
                    ]
                )
                name = f"{name_base}_{event_hooks_count}"

            script_path = self._create_template(hook_type, name)
            command = f"python {script_path}"

        if not command and not script_path:
            raise ValueError("Must provide either --command, --script, or --template")

        final_command = command or f"python {script_path}"

        # Add hook to settings
        event_hooks = hooks_config.setdefault(event_name, [])

        # Find existing matcher or create new one
        matcher_config = None
        for config in event_hooks:
            if config.get("matcher") == matcher:
                matcher_config = config
                break

        if not matcher_config:
            matcher_config = {"matcher": matcher, "hooks": []}
            event_hooks.append(matcher_config)

        hook_config = {"type": "command", "command": final_command}

        matcher_config["hooks"].append(hook_config)
        self._save_settings(settings)

        return str(script_path) if template and script_path else final_command

    def remove_hook(self, identifier: str) -> bool:
        """Remove a hook by index or identifier."""
        settings = self._load_settings()
        settings.get("hooks", {})

        try:
            # Try to parse as index
            index = int(identifier)
            hooks = self.list_hooks()
            if 0 <= index < len(hooks):
                hook_to_remove = hooks[index]
                return self._remove_hook_by_details(settings, hook_to_remove)
        except ValueError:
            # Not an index, try other identifiers
            pass

        return False

    def _remove_hook_by_details(
        self, settings: dict[str, Any], hook: dict[str, Any]
    ) -> bool:
        """Remove a specific hook by its details."""
        hooks_config = settings.get("hooks", {})
        event_name = hook["event"]

        if event_name not in hooks_config:
            return False

        for matcher_config in hooks_config[event_name]:
            if matcher_config.get("matcher") == hook["matcher"]:
                hooks = matcher_config.get("hooks", [])
                for i, h in enumerate(hooks):
                    if h.get("command") == hook["command"]:
                        hooks.pop(i)
                        if not hooks:
                            # Remove empty matcher config
                            hooks_config[event_name].remove(matcher_config)
                            if not hooks_config[event_name]:
                                # Remove empty event
                                del hooks_config[event_name]
                        self._save_settings(settings)
                        return True

        return False

    def run_hook(
        self, identifier: str, test_input: str | None = None, dry_run: bool = False
    ) -> None:
        """Run/test a hook."""
        hooks = self.list_hooks()

        try:
            index = int(identifier)
            if 0 <= index < len(hooks):
                hook = hooks[index]
                command = hook["command"]

                if dry_run:
                    click.echo(f"Would run: {command}")
                    if test_input:
                        click.echo(f"With input: {test_input}")
                    return

                # Run the hook
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                stdout, stderr = proc.communicate(input=test_input)

                click.echo(f"Exit code: {proc.returncode}")
                if stdout:
                    click.echo(f"STDOUT:\n{stdout}")
                if stderr:
                    click.echo(f"STDERR:\n{stderr}")

        except (ValueError, IndexError):
            click.echo(f"Invalid hook identifier: {identifier}")

    def _create_template(self, hook_type: str, name: str) -> str:
        """Create a cchooks Python template."""
        script_path = self.hooks_dir / f"{name}.py"

        # Convert hook type to context class name
        context_map = {
            "PreToolUse": "PreToolUseContext",
            "PostToolUse": "PostToolUseContext",
            "Notification": "NotificationContext",
            "Stop": "StopContext",
            "SubagentStop": "SubagentStopContext",
            "UserPromptSubmit": "UserPromptSubmitContext",
            "PreCompact": "PreCompactContext",
            "SessionStart": "SessionStartContext",
            "SessionEnd": "SessionEndContext",
        }

        context_class = context_map.get(hook_type, "PreToolUseContext")

        template = f'''#!/usr/bin/env python3
"""
{name.replace("_", " ").title()} hook for Claude Code.
Generated by clod hooks.
"""

from cchooks import create_context, {context_class}

# Create context - this handles all the input parsing
c = create_context()
assert isinstance(c, {context_class})

# Your hook logic here
# Examples:
# - Block dangerous commands: c.output.exit_block("Reason")
# - Approve: c.output.exit_success()
# - Log information: print(f"Tool: {{c.tool_name}}", file=sys.stderr)

# For now, just approve everything
c.output.exit_success()
'''

        with script_path.open("w") as f:
            f.write(template)

        # Make executable
        script_path.chmod(0o755)

        return str(script_path)

    def _normalize_event_name(self, hook_type: str) -> str:
        """Convert hook type to Claude Code event name format."""
        # Convert kebab-case to PascalCase
        parts = hook_type.split("-")
        return "".join(word.capitalize() for word in parts)
