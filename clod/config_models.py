"""Pydantic models for clod package."""

from datetime import datetime
from typing import Any, Literal

from claude_code_sdk import McpServerConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClaudeDesktopConfig(BaseModel):
    """Claude Desktop configuration schema."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    mcp_servers: dict[str, McpServerConfig] = Field(
        default_factory=dict, alias="mcpServers"
    )
    mcp_servers_disabled: dict[str, Any] = Field(
        default_factory=dict, alias="mcpServersDisabled"
    )


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

    model_config = ConfigDict(extra="allow")

    hooks: dict[str, list[HookMatcher]] = Field(default_factory=dict)


# Claude Code Settings Models
class PermissionsConfig(BaseModel):
    """Claude Code permissions configuration."""

    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)
    additional_directories: list[str] = Field(
        default_factory=list, alias="additionalDirectories"
    )
    default_mode: Literal["allow", "deny", "ask"] | None = Field(
        default=None, alias="defaultMode"
    )
    disable_bypass_permissions_mode: bool = Field(
        default=False, alias="disableBypassPermissionsMode"
    )

    @field_validator("allow", "deny")
    @classmethod
    def validate_permission_patterns(cls, v: list[str]) -> list[str]:
        """Validate permission patterns."""
        for pattern in v:
            if not pattern:
                raise ValueError("Empty permission pattern")
            # Basic validation for tool patterns like "Bash(command)", "Read(path)"
            if "(" in pattern and not pattern.endswith(")"):
                raise ValueError(f"Invalid permission pattern: {pattern}")
        return v


class ClaudeCodeHook(BaseModel):
    """Individual hook in Claude Code settings."""

    type: Literal["command"] = "command"
    command: str = Field(min_length=1)


class ClaudeCodeHookMatcher(BaseModel):
    """Hook matcher in Claude Code settings."""

    matcher: str = Field(min_length=1)
    hooks: list[ClaudeCodeHook] = Field(default_factory=list)


class ClaudeCodeSettings(BaseModel):
    """Claude Code settings.json schema."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Authentication and Model
    api_key_helper: str | None = Field(default=None, alias="apiKeyHelper")
    model: str | None = None
    force_login_method: Literal["anthropic", "google", "sso"] | None = Field(
        default=None, alias="forceLoginMethod"
    )

    # System Configuration
    cleanup_period_days: int = Field(default=30, alias="cleanupPeriodDays", ge=1)
    include_co_authored_by: bool = Field(default=True, alias="includeCoAuthoredBy")

    # Environment Variables
    env: dict[str, str] = Field(default_factory=dict)

    # Permissions
    permissions: PermissionsConfig | None = None

    # Hooks
    hooks: dict[str, list[ClaudeCodeHookMatcher]] = Field(default_factory=dict)

    # MCP Server Configuration
    enable_all_project_mcp_servers: bool = Field(
        default=False, alias="enableAllProjectMcpServers"
    )
    enabled_mcpjson_servers: list[str] = Field(
        default_factory=list, alias="enabledMcpjsonServers"
    )
    disabled_mcpjson_servers: list[str] = Field(
        default_factory=list, alias="disabledMcpjsonServers"
    )

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        """Validate model identifier."""
        if v is not None and not v.strip():
            raise ValueError("Model identifier cannot be empty")
        return v

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate environment variables."""
        for key, value in v.items():
            if not key:
                raise ValueError("Environment variable key cannot be empty")
            if not isinstance(value, str):
                raise ValueError(f"Environment variable value must be string: {key}")
        return v

    @field_validator("hooks")
    @classmethod
    def validate_hooks(
        cls, v: dict[str, list[ClaudeCodeHookMatcher]]
    ) -> dict[str, list[ClaudeCodeHookMatcher]]:
        """Validate hooks configuration."""
        valid_hook_types = [
            "PreToolUse",
            "PostToolUse",
            "UserPromptSubmit",
            "AssistantResponseGenerated",
            "ConversationDeleted",
            "ConversationContinued",
            "ConversationCreated",
        ]
        for hook_type in v:
            if hook_type not in valid_hook_types:
                raise ValueError(
                    f"Invalid hook type: {hook_type}. "
                    f"Valid types: {', '.join(valid_hook_types)}"
                )
        return v
