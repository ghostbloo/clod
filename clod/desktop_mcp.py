"""Claude Desktop MCP server management."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from claude_code_sdk import McpServerConfig

if TYPE_CHECKING:
    from claude_code_sdk.types import McpStdioServerConfig

from .config_models import ClaudeDesktopConfig


class ClaudeDesktopMcpManager:
    """Manager for Claude Desktop MCP servers."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or (
            Path.home()
            / "Library/Application Support/Claude/claude_desktop_config.json"
        )

    def _read_config(self) -> ClaudeDesktopConfig:
        """Read the Claude Desktop configuration."""
        if not self.config_path.exists():
            return ClaudeDesktopConfig()

        try:
            with self.config_path.open() as f:
                data = json.load(f)
            return ClaudeDesktopConfig(**data)
        except (json.JSONDecodeError, Exception):
            return ClaudeDesktopConfig()

    def _write_config(self, config: ClaudeDesktopConfig) -> None:
        """Write the Claude Desktop configuration."""
        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with self.config_path.open("w") as f:
            json.dump(config.model_dump(by_alias=True), f, indent=2)

    def list_servers(self) -> dict[str, McpServerConfig]:
        """List all configured MCP servers."""
        config = self._read_config()
        return config.mcp_servers

    def get_server(self, name: str) -> McpServerConfig | None:
        """Get a specific MCP server configuration."""
        config = self._read_config()
        return config.mcp_servers.get(name)

    def add_server(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Add a new MCP server."""
        config = self._read_config()
        server_config: McpStdioServerConfig = {
            "type": "stdio",
            "command": command,
        }
        if args:
            server_config["args"] = args
        if env:
            server_config["env"] = env

        config.mcp_servers[name] = server_config
        self._write_config(config)

    def remove_server(self, name: str) -> bool:
        """Remove an MCP server."""
        config = self._read_config()
        if name in config.mcp_servers:
            del config.mcp_servers[name]
            self._write_config(config)
            return True
        return False

    def enable_server(self, name: str) -> bool:
        """Enable a disabled MCP server."""
        config = self._read_config()
        if name in config.mcp_servers_disabled:
            # Move from disabled to enabled
            server_config = config.mcp_servers_disabled.pop(name)
            config.mcp_servers[name] = server_config  # Already a dict
            self._write_config(config)
            return True
        return False

    def disable_server(self, name: str) -> bool:
        """Disable an MCP server."""
        config = self._read_config()
        if name in config.mcp_servers:
            # Move from enabled to disabled
            server_config = config.mcp_servers.pop(name)
            # Convert to dict (though it already is)
            config.mcp_servers_disabled[name] = dict(server_config)
            self._write_config(config)
            return True
        return False
