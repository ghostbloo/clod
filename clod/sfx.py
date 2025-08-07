"""Sound effects management for Claude Code."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Footer, Header, ListItem, ListView, Static


class SoundPlayer:
    """Cross-platform sound player."""

    def __init__(self) -> None:
        self.current_process: subprocess.Popen | None = None

    def play(self, sound_path: Path) -> bool:
        """Play a sound file."""
        # Kill previous sound if still playing
        self.stop()

        try:
            if sys.platform == "darwin":
                # macOS
                self.current_process = subprocess.Popen(
                    ["afplay", str(sound_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif sys.platform.startswith("linux"):
                # Linux - try common players
                for player in ["aplay", "paplay", "ffplay"]:
                    if self._command_exists(player):
                        self.current_process = subprocess.Popen(
                            [player, str(sound_path)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        break
                else:
                    return False
            elif sys.platform == "win32":
                # Windows
                import winsound

                winsound.PlaySound(
                    str(sound_path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC,
                )
                return True
            else:
                return False

            return True

        except (FileNotFoundError, OSError):
            return False

    def stop(self) -> None:
        """Stop currently playing sound."""
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
            except Exception:
                pass
            finally:
                self.current_process = None

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH."""
        import shutil

        return shutil.which(command) is not None


class SoundEffectsManager:
    """Manages Claude Code sound effects configuration."""

    HOOK_TYPES: ClassVar[list[str]] = [
        "PreToolUse",
        "PostToolUse",
        "Notification",
        "Stop",
        "SubagentStop",
        "UserPromptSubmit",
        "PreCompact",
    ]

    def __init__(
        self, settings_path: Path | None = None, sounds_path: Path | None = None
    ) -> None:
        self.settings_path = settings_path or Path.home() / ".claude" / "settings.json"
        self.sounds_path = sounds_path or Path.home() / ".claude" / "sounds"

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

    def get_sound_files(self) -> list[Path]:
        """Get all sound files from the sounds directory."""
        if not self.sounds_path.exists():
            return []

        sound_extensions = {".wav", ".mp3", ".m4a", ".aiff", ".au", ".flac"}
        sound_files = []

        for file_path in self.sounds_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in sound_extensions:
                sound_files.append(file_path)

        return sorted(sound_files, key=lambda p: p.name.lower())

    def get_current_mappings(self) -> dict[str, dict[str, str]]:
        """Get current hook -> sound mappings."""
        settings = self._load_settings()
        mappings = {}

        for hook_type, matchers in settings.get("hooks", {}).items():
            if hook_type in self.HOOK_TYPES:
                for matcher_config in matchers:
                    matcher = matcher_config.get("matcher", "*")
                    for hook in matcher_config.get("hooks", []):
                        command = hook.get("command", "")
                        is_sound_command = "afplay" in command and (
                            "~/.claude/sounds/" in command
                            or "/.claude/sounds/" in command
                        )
                        if is_sound_command:
                            # Extract sound file name from command
                            sound_file = self._extract_sound_from_command(command)
                            if sound_file:
                                key = f"{hook_type}:{matcher}"
                                mappings[key] = {
                                    "hook_type": hook_type,
                                    "matcher": matcher,
                                    "sound": sound_file,
                                }

        return mappings

    def _extract_sound_from_command(self, command: str) -> str | None:
        """Extract sound file name from afplay command."""
        import re

        # Handle both quoted and unquoted paths, both relative (~) and absolute
        patterns = [
            r'afplay\s+"?~/.claude/sounds/([^"&]+)"?',
            r"afplay\s+~/.claude/sounds/([^&\s]+)",
            r'afplay\s+"?/[^"]*/.claude/sounds/([^"&]+)"?',
            r"afplay\s+/[^&\s]*/.claude/sounds/([^&\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1).strip('"')

        return None

    def set_sound_mapping(self, hook_type: str, matcher: str, sound_file: str) -> bool:
        """Set sound mapping for a hook type and matcher."""
        settings = self._load_settings()
        hooks_config = settings.setdefault("hooks", {})

        # Prepare the command using relative path for consistency
        sound_path = self.sounds_path / sound_file
        if not sound_path.exists():
            return False

        # Use relative path for consistency with existing hooks
        relative_path = f"~/.claude/sounds/{sound_file}"

        # Quote the path if it contains spaces
        if " " in sound_file:
            command = f'afplay "{relative_path}" &'
        else:
            command = f"afplay {relative_path} &"

        # Find or create the hook configuration
        event_hooks = hooks_config.setdefault(hook_type, [])

        # Find existing matcher or create new one
        matcher_config = None
        for config in event_hooks:
            if config.get("matcher") == matcher:
                matcher_config = config
                break

        if not matcher_config:
            matcher_config = {"matcher": matcher, "hooks": []}
            event_hooks.append(matcher_config)

        # Remove any existing sound hooks for this matcher
        hooks = matcher_config.get("hooks", [])
        new_hooks = []
        for h in hooks:
            cmd = h.get("command", "")
            is_afplay_sound = cmd.startswith("afplay") and "~/.claude/sounds/" in cmd
            if not is_afplay_sound:
                new_hooks.append(h)
        matcher_config["hooks"] = new_hooks

        # Add the new sound hook
        hook_config = {"type": "command", "command": command}

        matcher_config["hooks"].append(hook_config)
        self._save_settings(settings)

        return True

    def remove_sound_mapping(self, hook_type: str, matcher: str) -> bool:
        """Remove sound mapping for a hook type and matcher."""
        settings = self._load_settings()
        hooks_config = settings.get("hooks", {})

        if hook_type not in hooks_config:
            return False

        for matcher_config in hooks_config[hook_type]:
            if matcher_config.get("matcher") == matcher:
                # Remove sound hooks
                hooks = matcher_config.get("hooks", [])
                original_length = len(hooks)
                new_hooks = []
                for h in hooks:
                    cmd = h.get("command", "")
                    is_sound_hook = cmd.startswith("afplay") and (
                        "~/.claude/sounds/" in cmd or "/.claude/sounds/" in cmd
                    )
                    if not is_sound_hook:
                        new_hooks.append(h)
                matcher_config["hooks"] = new_hooks

                # If we removed something, save and return success
                if len(matcher_config["hooks"]) < original_length:
                    # Clean up empty configurations
                    if not matcher_config["hooks"]:
                        hooks_config[hook_type].remove(matcher_config)
                        if not hooks_config[hook_type]:
                            del hooks_config[hook_type]

                    self._save_settings(settings)
                    return True

        return False


class SoundEffectsTUI(App):
    """Interactive TUI for configuring sound effects."""

    CSS = """
    Screen {
        layout: horizontal;
    }

    .left-panel {
        width: 40%;
        height: 100%;
        border: solid $primary;
        margin: 1;
    }

    .right-panel {
        width: 60%;
        height: 100%;
        border: solid $primary;
        margin: 1;
    }

    .panel-title {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-align: center;
        dock: top;
    }

    ListView {
        height: 1fr;
    }

    .status {
        height: 3;
        background: $surface;
        padding: 1;
        dock: bottom;
    }
    """

    BINDINGS: ClassVar = [
        ("q", "quit", "Quit"),
        ("space", "select", "Select"),
        ("d", "delete", "Delete mapping"),
    ]

    selected_hook = reactive("")
    selected_sound = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self.manager = SoundEffectsManager()
        self.player = SoundPlayer()
        self.hooks_list: list[dict[str, str]] = []
        self.sounds_list: list[dict[str, str]] = []
        self.current_mappings: dict[str, dict[str, str]] = {}

    def compose(self) -> ComposeResult:
        """Create the TUI layout."""
        with Container(classes="left-panel"):
            yield Static("Hooks", classes="panel-title")
            yield ListView(id="hooks-list")

        with Container(classes="right-panel"):
            yield Static("Sounds", classes="panel-title")
            yield ListView(id="sounds-list")

        yield Header()
        yield Footer()
        yield Static(
            "Select a hook on the left, then choose a sound on the right. "
            "Press Space to assign.",
            classes="status",
            id="status",
        )

    async def on_mount(self) -> None:
        """Initialize the app."""
        self._load_data()
        await self._populate_lists()

    def _load_data(self) -> None:
        """Load hooks and sounds data."""
        # Load all possible hook types and matchers
        self.current_mappings = self.manager.get_current_mappings()

        # Create hooks list - include common hook+matcher combinations
        self.hooks_list = []
        common_matchers = ["*", "Bash", "Edit", "Write", "Task", "Grep|Glob|LS"]

        for hook_type in self.manager.HOOK_TYPES:
            for matcher in common_matchers:
                key = f"{hook_type}:{matcher}"
                current_sound = ""
                if key in self.current_mappings:
                    current_sound = f" -> {self.current_mappings[key]['sound']}"

                display_matcher = matcher or "(empty)"
                self.hooks_list.append(
                    {
                        "key": key,
                        "display": f"{hook_type} | {display_matcher}{current_sound}",
                        "hook_type": hook_type,
                        "matcher": matcher,
                    }
                )

        # Load sound files
        self.sounds_list = [
            {"path": str(sound_path), "name": sound_path.name}
            for sound_path in self.manager.get_sound_files()
        ]

    async def _populate_lists(self) -> None:
        """Populate the ListView widgets."""
        hooks_list = self.query_one("#hooks-list", ListView)
        sounds_list = self.query_one("#sounds-list", ListView)

        await hooks_list.clear()
        await sounds_list.clear()

        for i, hook in enumerate(self.hooks_list):
            hooks_list.append(ListItem(Static(hook["display"]), id=f"hook-{i}"))

        for i, sound in enumerate(self.sounds_list):
            sounds_list.append(ListItem(Static(sound["name"]), id=f"sound-{i}"))

    @on(ListView.Highlighted)
    def on_list_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle list item highlighting."""
        if event.list_view.id == "hooks-list" and event.item and event.item.id:
            # Extract index from hook-{i} format
            try:
                index = int(event.item.id.split("-")[1])
                if 0 <= index < len(self.hooks_list):
                    self.selected_hook = self.hooks_list[index]["key"]
                    self._update_status()
            except (ValueError, IndexError):
                pass
        elif event.list_view.id == "sounds-list" and event.item and event.item.id:
            # Extract index from sound-{i} format
            try:
                index = int(event.item.id.split("-")[1])
                if 0 <= index < len(self.sounds_list):
                    self.selected_sound = self.sounds_list[index]["name"]
                    self._play_sound_preview(self.selected_sound)
                    self._update_status()
            except (ValueError, IndexError):
                pass

    def _play_sound_preview(self, sound_name: str) -> None:
        """Play a sound preview."""
        sound_path = self.manager.sounds_path / sound_name
        if sound_path.exists():
            self.player.play(sound_path)

    def _update_status(self) -> None:
        """Update the status bar."""
        status = self.query_one("#status", Static)

        if self.selected_hook and self.selected_sound:
            hook_data = next(
                (h for h in self.hooks_list if h["key"] == self.selected_hook), None
            )
            if hook_data:
                matcher_display = hook_data["matcher"] or "(empty)"
                msg = (
                    f"Ready to assign '{self.selected_sound}' to "
                    f"{hook_data['hook_type']} | {matcher_display}. Press Space."
                )
                status.update(msg)
        elif self.selected_hook:
            status.update(
                f"Hook selected: {self.selected_hook}. Choose a sound on the right."
            )
        elif self.selected_sound:
            status.update(
                f"Sound selected: {self.selected_sound}. Choose a hook on the left."
            )
        else:
            status.update(
                "Select a hook on the left, then choose a sound on the right. "
                "Press Space to assign."
            )

    async def action_select(self) -> None:
        """Assign selected sound to selected hook."""
        if not self.selected_hook or not self.selected_sound:
            return

        hook_data = next(
            (h for h in self.hooks_list if h["key"] == self.selected_hook), None
        )
        if not hook_data:
            return

        success = self.manager.set_sound_mapping(
            hook_data["hook_type"], hook_data["matcher"], self.selected_sound
        )

        if success:
            # Refresh the data and UI
            self._load_data()
            await self._populate_lists()

            status = self.query_one("#status", Static)
            matcher_display = hook_data["matcher"] or "(empty)"
            msg = (
                f"✓ Assigned '{self.selected_sound}' to "
                f"{hook_data['hook_type']} | {matcher_display}"
            )
            status.update(msg)
        else:
            status = self.query_one("#status", Static)
            status.update("✗ Failed to assign sound")

    async def action_delete(self) -> None:
        """Remove sound mapping for selected hook."""
        if not self.selected_hook:
            return

        hook_data = next(
            (h for h in self.hooks_list if h["key"] == self.selected_hook), None
        )
        if not hook_data:
            return

        success = self.manager.remove_sound_mapping(
            hook_data["hook_type"], hook_data["matcher"]
        )

        if success:
            # Refresh the data and UI
            self._load_data()
            await self._populate_lists()

            status = self.query_one("#status", Static)
            matcher_display = hook_data["matcher"] or "(empty)"
            msg = (
                f"✓ Removed sound mapping for "
                f"{hook_data['hook_type']} | {matcher_display}"
            )
            status.update(msg)
        else:
            status = self.query_one("#status", Static)
            status.update("✗ No sound mapping found to remove")

    async def action_quit(self) -> None:
        """Quit the application."""
        self.player.stop()
        self.exit()


def run_tui() -> None:
    """Run the sound effects TUI."""
    app = SoundEffectsTUI()
    app.run()
