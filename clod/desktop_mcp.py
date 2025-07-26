"""Claude Desktop MCP server management."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class McpServer(BaseModel):
    """Configuration for a single MCP server."""
    type: str = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)


class ClaudeDesktopConfig(BaseModel):
    """Claude Desktop configuration schema."""
    mcpServers: Dict[str, McpServer] = Field(default_factory=dict)
    mcpServersDisabled: Dict[str, Any] = Field(default_factory=dict)


class ClaudeDesktopMcpManager:
    """Manager for Claude Desktop MCP servers."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (
            Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
        )
    
    def _read_config(self) -> ClaudeDesktopConfig:
        """Read the Claude Desktop configuration."""
        if not self.config_path.exists():
            return ClaudeDesktopConfig()
        
        try:
            with open(self.config_path, 'r') as f:
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
    
    def list_servers(self) -> Dict[str, McpServer]:
        """List all configured MCP servers."""
        config = self._read_config()
        return config.mcpServers
    
    def get_server(self, name: str) -> Optional[McpServer]:
        """Get a specific MCP server configuration."""
        config = self._read_config()
        return config.mcpServers.get(name)
    
    def add_server(self, name: str, command: str, args: Optional[list[str]] = None, 
                   env: Optional[Dict[str, str]] = None) -> None:
        """Add a new MCP server."""
        config = self._read_config()
        config.mcpServers[name] = McpServer(
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
            config.mcpServers[name] = McpServer(**server_config)
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