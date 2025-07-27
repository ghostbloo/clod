"""Claude Desktop MCP server management."""

import json
from pathlib import Path

from .models import ClaudeDesktopConfig, McpServer, McpStdioServer, McpSseServer, McpHttpServer


class ClaudeDesktopMcpManager:
    """Manager for Claude Desktop MCP servers."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or (
            Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
        )

    def _read_config(self) -> ClaudeDesktopConfig:
        """Read the Claude Desktop configuration."""
        if not self.config_path.exists():
            return ClaudeDesktopConfig()

        try:
            with open(self.config_path) as f:
                data = json.load(f)
            return ClaudeDesktopConfig(**data)
        except (json.JSONDecodeError, Exception):
            return ClaudeDesktopConfig()

    def _write_config(self, config: ClaudeDesktopConfig) -> None:
        """Write the Claude Desktop configuration."""
        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, 'w') as f:
            json.dump(config.model_dump(), f, indent=2)

    def _create_server_from_config(self, server_config: dict) -> McpServer:
        """Create the appropriate McpServer type from configuration dictionary."""
        server_type = server_config.get("type", "stdio")
        
        if server_type == "stdio":
            return McpStdioServer(**server_config)
        elif server_type == "sse":
            return McpSseServer(**server_config)
        elif server_type == "http":
            return McpHttpServer(**server_config)
        else:
            # Default to stdio for unknown types
            return McpStdioServer(**server_config)

    def list_servers(self) -> dict[str, McpServer]:
        """List all configured MCP servers."""
        config = self._read_config()
        return config.mcpServers

    def get_server(self, name: str) -> McpServer | None:
        """Get a specific MCP server configuration."""
        config = self._read_config()
        return config.mcpServers.get(name)

    def add_server(self, name: str, command: str, args: list[str] | None = None,
                   env: dict[str, str] | None = None) -> None:
        """Add a new MCP server."""
        config = self._read_config()
        config.mcpServers[name] = McpStdioServer(
            command=command,
            args=args or [],
            env=env or {}
        )
        self._write_config(config)

    def remove_server(self, name: str) -> bool:
        """Remove an MCP server."""
        config = self._read_config()
        if name in config.mcpServers:
            del config.mcpServers[name]
            self._write_config(config)
            return True
        return False

    def enable_server(self, name: str) -> bool:
        """Enable a disabled MCP server."""
        config = self._read_config()
        if name in config.mcpServersDisabled:
            # Move from disabled to enabled
            server_config = config.mcpServersDisabled.pop(name)
            config.mcpServers[name] = self._create_server_from_config(server_config)
            self._write_config(config)
            return True
        return False

    def disable_server(self, name: str) -> bool:
        """Disable an MCP server."""
        config = self._read_config()
        if name in config.mcpServers:
            # Move from enabled to disabled
            server_config = config.mcpServers.pop(name)
            config.mcpServersDisabled[name] = server_config.model_dump()
            self._write_config(config)
            return True
        return False
