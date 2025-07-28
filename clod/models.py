"""Pydantic models for clod package."""

from datetime import datetime
from typing import Any, Literal

from claude_code_sdk import McpServerConfig
from pydantic import BaseModel, ConfigDict, Field


class ClaudeDesktopConfig(BaseModel):
    """Claude Desktop configuration schema."""
    model_config = ConfigDict(extra='allow')

    mcpServers: dict[str, McpServerConfig] = Field(default_factory=dict)
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
