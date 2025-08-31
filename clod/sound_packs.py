"""Sound pack management for Claude Code and Opencode."""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, ValidationError

from .sfx import SoundEffectsManager

OpencodeEvent = Literal[
    "installation.updated",
    "lsp.client.diagnostics",
    "message.updated",
    "message.removed",
    "message.part.updated",
    "message.part.removed",
    "storage.write",
    "file.edited",
    "server.connected",
    "permission.updated",
    "permission.replied",
    "session.updated",
    "session.deleted",
    "session.idle",
    "session.error",
    "file.watcher.updated",
    "ide.installed",
]


class SoundPackEvent(BaseModel):
    """Individual sound effect mapping for an event."""

    sound_file: str = Field(..., description="Path to sound file within the pack")
    enabled: bool = Field(default=True, description="Whether this event is enabled")
    volume: float = Field(default=1.0, ge=0.0, le=1.0, description="Volume level")


class SoundPackSchema(BaseModel):
    """Schema for sound effect pack configuration."""

    name: str = Field(..., description="Display name of the sound pack")
    version: str = Field(default="1.0.0", description="Version of the sound pack")
    description: str = Field(default="", description="Description of the sound pack")
    author: str = Field(default="", description="Author of the sound pack")

    # Event mappings using Opencode event names (more comprehensive)
    events: dict[str, SoundPackEvent] = Field(
        default_factory=dict,
        description="Event to sound mappings using Opencode event names",
    )

    # Metadata
    created_at: str | None = Field(default=None, description="Creation timestamp")
    updated_at: str | None = Field(default=None, description="Last update timestamp")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class SoundPackManager:
    """Manages sound pack installation and integration."""

    # Event mapping between Claude Code and Opencode
    EVENT_MAPPING: ClassVar[dict[str, str]] = {
        # Claude Code -> Opencode
        "PreToolUse": "tool.execute.before",
        "PostToolUse": "tool.execute.after",
        "Notification": "chat.message",
        "Stop": "session.idle",
        "SubagentStop": "session.idle",
        "UserPromptSubmit": "chat.message",
        "PreCompact": "session.idle",
    }

    # Reverse mapping for Opencode -> Claude Code
    REVERSE_EVENT_MAPPING: ClassVar[dict[str, str]] = {
        v: k for k, v in EVENT_MAPPING.items()
    }

    # All supported Opencode events
    OPENCODE_EVENTS: ClassVar[list[str]] = []

    def __init__(self) -> None:
        self.config_dir = Path.home() / ".config" / "clod"
        self.sounds_dir = self.config_dir / "sounds"
        self.sounds_dir.mkdir(parents=True, exist_ok=True)

        self.claude_sounds_dir = Path.home() / ".claude" / "sounds"
        self.opencode_plugin_dir = Path.home() / ".opencode" / "plugin"

    def install_pack(self, pack_path: Path, pack_name: str | None = None) -> bool:
        """Install a sound pack from a zip archive or directory."""
        if pack_path.suffix.lower() == ".zip":
            return self._install_from_zip(pack_path, pack_name)
        elif pack_path.is_dir():
            return self._install_from_directory(pack_path, pack_name)
        else:
            raise ValueError("Pack path must be a zip file or directory")

    def _install_from_zip(self, zip_path: Path, pack_name: str | None = None) -> bool:
        """Install sound pack from zip archive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract zip
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_path)

            # Find sounds.json
            sounds_json_path = None
            for root_dir in temp_path.iterdir():
                if root_dir.is_dir():
                    potential_json = root_dir / "sounds.json"
                    if potential_json.exists():
                        sounds_json_path = potential_json
                        temp_path = root_dir
                        break

            if not sounds_json_path:
                sounds_json_path = temp_path / "sounds.json"

            if not sounds_json_path.exists():
                raise FileNotFoundError("sounds.json not found in pack")

            return self._install_from_directory(temp_path, pack_name)

    def _install_from_directory(
        self, dir_path: Path, pack_name: str | None = None
    ) -> bool:
        """Install sound pack from directory."""
        sounds_json_path = dir_path / "sounds.json"
        if not sounds_json_path.exists():
            raise FileNotFoundError(f"sounds.json not found in {dir_path}")

        # Load and validate schema
        try:
            with sounds_json_path.open() as f:
                pack_data = json.load(f)
            pack_schema = SoundPackSchema(**pack_data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Invalid sound pack schema: {e}") from e

        # Determine pack name
        final_pack_name = pack_name or pack_schema.name.lower().replace(" ", "-")
        pack_install_dir = self.sounds_dir / final_pack_name

        # Create installation directory
        if pack_install_dir.exists():
            shutil.rmtree(pack_install_dir)
        pack_install_dir.mkdir(parents=True)

        # Copy sounds.json
        shutil.copy2(sounds_json_path, pack_install_dir)

        # Copy sound files
        for _event_name, event_config in pack_schema.events.items():
            sound_file_path = dir_path / event_config.sound_file
            if sound_file_path.exists():
                dest_path = pack_install_dir / event_config.sound_file
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sound_file_path, dest_path)

        return True

    def list_installed_packs(self) -> list[dict[str, Any]]:
        """List all installed sound packs."""
        packs = []

        for pack_dir in self.sounds_dir.iterdir():
            if pack_dir.is_dir():
                sounds_json = pack_dir / "sounds.json"
                if sounds_json.exists():
                    try:
                        with sounds_json.open() as f:
                            pack_data = json.load(f)
                        pack_schema = SoundPackSchema(**pack_data)
                        packs.append(
                            {
                                "name": pack_schema.name,
                                "version": pack_schema.version,
                                "description": pack_schema.description,
                                "author": pack_schema.author,
                                "pack_dir": str(pack_dir),
                                "installed_name": pack_dir.name,
                            }
                        )
                    except (json.JSONDecodeError, ValidationError):
                        continue

        return packs

    def get_pack_schema(self, pack_name: str) -> SoundPackSchema | None:
        """Get schema for an installed pack."""
        pack_dir = self.sounds_dir / pack_name
        sounds_json = pack_dir / "sounds.json"

        if not sounds_json.exists():
            return None

        try:
            with sounds_json.open() as f:
                pack_data = json.load(f)
            return SoundPackSchema(**pack_data)
        except (json.JSONDecodeError, ValidationError):
            return None

    def enable_for_claude_code(self, pack_name: str, matcher: str = "*") -> bool:
        """Enable sound pack for Claude Code."""
        pack_schema = self.get_pack_schema(pack_name)
        if not pack_schema:
            return False

        pack_dir = self.sounds_dir / pack_name
        sfx_manager = SoundEffectsManager()

        # Ensure Claude sounds directory exists and copy sounds
        self.claude_sounds_dir.mkdir(parents=True, exist_ok=True)

        for event_name, event_config in pack_schema.events.items():
            if not event_config.enabled:
                continue

            # Map Opencode event to Claude Code event
            claude_event = self.REVERSE_EVENT_MAPPING.get(event_name)
            if not claude_event:
                continue

            # Copy sound file to Claude sounds directory
            source_path = pack_dir / event_config.sound_file
            dest_path = (
                self.claude_sounds_dir / f"{pack_name}_{event_config.sound_file}"
            )

            if source_path.exists():
                shutil.copy2(source_path, dest_path)

                # Set up sound mapping
                sfx_manager.set_sound_mapping(claude_event, matcher, dest_path.name)

        return True

    def enable_for_opencode(self, pack_name: str) -> bool:
        """Enable sound pack for Opencode."""
        pack_schema = self.get_pack_schema(pack_name)
        if not pack_schema:
            return False

        pack_dir = self.sounds_dir / pack_name
        self.opencode_plugin_dir.mkdir(parents=True, exist_ok=True)

        # Create Opencode plugin script
        plugin_script = self._generate_opencode_plugin(pack_name, pack_schema, pack_dir)
        plugin_path = self.opencode_plugin_dir / f"clod-sounds-{pack_name}.js"

        with plugin_path.open("w") as f:
            f.write(plugin_script)

        return True

    def _generate_opencode_plugin(
        self,
        pack_name: str,
        pack_schema: SoundPackSchema,
        pack_dir: Path,
    ) -> str:
        """Generate Opencode plugin script for sound pack."""

        # Build event mappings
        event_mappings = {}
        for event_name, event_config in pack_schema.events.items():
            if event_config.enabled and event_name in self.OPENCODE_EVENTS:
                sound_path = pack_dir / event_config.sound_file
                if sound_path.exists():
                    event_mappings[event_name] = {
                        "sound_file": str(sound_path.absolute()),
                        "volume": event_config.volume,
                    }

        sfx_plugin_path: Path = self.opencode_plugin_dir / "sfx.ts"
        if sfx_plugin_path.exists() is False:
            raise FileNotFoundError("sfx.ts not found in .opencode/plugin/")

        return sfx_plugin_path.read_text().replace(
            "// SOUND_MAPPINGS",
            f"const SOUND_MAPPINGS = {json.dumps(event_mappings, indent=2)};",
        )

    def disable_for_claude_code(self, pack_name: str) -> bool:
        """Disable sound pack for Claude Code."""
        sfx_manager = SoundEffectsManager()

        # Remove sound files that start with pack name
        if self.claude_sounds_dir.exists():
            for sound_file in self.claude_sounds_dir.glob(f"{pack_name}_*"):
                sound_file.unlink(missing_ok=True)

        # Remove sound mappings
        mappings = sfx_manager.get_current_mappings()
        for _key, mapping in mappings.items():
            if mapping["sound"].startswith(f"{pack_name}_"):
                hook_type = mapping["hook_type"]
                matcher = mapping["matcher"]
                sfx_manager.remove_sound_mapping(hook_type, matcher)

        return True

    def disable_for_opencode(self, pack_name: str) -> bool:
        """Disable sound pack for Opencode."""
        plugin_path = self.opencode_plugin_dir / f"clod-sounds-{pack_name}.js"
        if plugin_path.exists():
            plugin_path.unlink()
            return True
        return False

    def uninstall_pack(self, pack_name: str) -> bool:
        """Uninstall a sound pack completely."""
        pack_dir = self.sounds_dir / pack_name

        if not pack_dir.exists():
            return False

        # Disable from both systems first
        self.disable_for_claude_code(pack_name)
        self.disable_for_opencode(pack_name)

        # Remove pack directory
        shutil.rmtree(pack_dir)

        return True
