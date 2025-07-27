"""Pydantic models for clod package."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# MCP Server Models
class McpStdioServer(BaseModel):
    """MCP stdio server configuration."""
    type: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class McpSseServer(BaseModel):
    """MCP SSE server configuration."""
    type: Literal["sse"]
    url: str
    headers: dict[str, str] = Field(default_factory=dict)


class McpHttpServer(BaseModel):
    """MCP HTTP server configuration."""
    type: Literal["http"]
    url: str
    headers: dict[str, str] = Field(default_factory=dict)


# Union type for all MCP server types
McpServer = McpStdioServer | McpSseServer | McpHttpServer


class ClaudeDesktopConfig(BaseModel):
    """Claude Desktop configuration schema."""
    model_config = ConfigDict(extra='allow')

    mcpServers: dict[str, McpServer] = Field(default_factory=dict)
    mcpServersDisabled: dict[str, Any] = Field(default_factory=dict)


# Chat Message Models (converted from dataclasses)
class ChatMessage(BaseModel):
    """Represents a chat message from Claude Desktop."""
    conversation_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    timestamp: datetime | None = None
    message_type: Literal["user", "assistant"] = "user"
    is_draft: bool = False


class Conversation(BaseModel):
    """Represents a conversation thread."""
    id: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(default_factory=list)
    last_activity: datetime | None = None


# Hook Configuration Models
class HookConfig(BaseModel):
    """Configuration for a single hook."""
    type: Literal["command"] = "command"
    command: str = Field(min_length=1)
    enabled: bool = True


class HookMatcher(BaseModel):
    """Hook matcher configuration."""
    matcher: str = Field(min_length=1)
    hooks: list[HookConfig] = Field(default_factory=list)


class HooksConfig(BaseModel):
    """Complete hooks configuration."""
    model_config = ConfigDict(extra='allow')

    hooks: dict[str, list[HookMatcher]] = Field(default_factory=dict)
