"""Pydantic models for Claude Code session log format."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role types."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class LogEntryType(str, Enum):
    """Log entry types."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    SUMMARY = "summary"


class ContentBlockType(str, Enum):
    """Content block types."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"


class LogLevel(str, Enum):
    """System message log levels."""

    INFO = "info"
    ERROR = "error"
    WARN = "warn"
    WARNING = "warning"
    DEBUG = "debug"


class TextContentBlock(BaseModel):
    """Text content block."""

    type: ContentBlockType = ContentBlockType.TEXT
    text: str


class ToolUseContentBlock(BaseModel):
    """Tool use content block."""

    type: ContentBlockType = ContentBlockType.TOOL_USE
    id: str
    name: str
    input: dict[str, Any]


class ToolResultContentBlock(BaseModel):
    """Tool result content block."""

    type: ContentBlockType = ContentBlockType.TOOL_RESULT
    tool_use_id: str
    content: str | list[dict[str, Any]]
    is_error: bool | None = None


class ThinkingContentBlock(BaseModel):
    """Thinking content block."""

    type: ContentBlockType = ContentBlockType.THINKING
    thinking: str
    signature: str | None = None


ContentBlock = (
    TextContentBlock
    | ToolUseContentBlock
    | ToolResultContentBlock
    | ThinkingContentBlock
)


class UsageMetrics(BaseModel):
    """Token usage metrics."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    service_tier: str | None = None


class Message(BaseModel):
    """Claude message content."""

    id: str | None = None
    type: str | None = None
    role: MessageRole
    model: str | None = None
    content: str | list[ContentBlock]
    stop_reason: str | None = None
    stop_sequence: str | None = None
    usage: UsageMetrics | None = None


class ToolUseResult(BaseModel):
    """Tool execution result details."""

    stdout: str | None = None
    stderr: str | None = None
    interrupted: bool | None = None
    is_image: bool | None = None
    old_todos: list[dict[str, Any]] | None = None
    new_todos: list[dict[str, Any]] | None = None


class ClaudeLogEntry(BaseModel):
    """A single Claude Code session log entry."""

    # Core identification (optional for summary entries)
    uuid: str | None = None
    session_id: str | None = Field(None, alias="sessionId")
    timestamp: datetime | None = None

    # Message hierarchy
    parent_uuid: str | None = Field(None, alias="parentUuid")
    is_sidechain: bool | None = Field(None, alias="isSidechain")

    # Entry classification
    type: LogEntryType
    user_type: str | None = Field(None, alias="userType")
    is_meta: bool | None = Field(None, alias="isMeta")

    # Environment context
    cwd: str | None = None
    version: str | None = None
    git_branch: str | None = Field(None, alias="gitBranch")

    # Message content
    message: Message | None = None
    content: str | None = None  # Direct content for system messages

    # Summary specific fields
    summary: str | None = None
    leaf_uuid: str | None = Field(None, alias="leafUuid")

    # Tool execution
    tool_use_id: str | None = Field(None, alias="toolUseID")
    tool_use_result: ToolUseResult | str | list[dict[str, Any]] | None = Field(
        None, alias="toolUseResult"
    )

    # Request correlation
    request_id: str | None = Field(None, alias="requestId")

    # System message specific
    level: LogLevel | None = None

    class Config:
        """Pydantic config."""

        populate_by_name = True
        use_enum_values = True


class ClaudeSession(BaseModel):
    """A complete Claude Code session with all log entries."""

    session_id: str
    entries: list[ClaudeLogEntry]

    @property
    def start_time(self) -> datetime | None:
        """Get session start time."""
        if not self.entries:
            return None
        timestamps = [entry.timestamp for entry in self.entries if entry.timestamp]
        return min(timestamps) if timestamps else None

    @property
    def end_time(self) -> datetime | None:
        """Get session end time."""
        if not self.entries:
            return None
        timestamps = [entry.timestamp for entry in self.entries if entry.timestamp]
        return max(timestamps) if timestamps else None

    @property
    def user_messages(self) -> list[ClaudeLogEntry]:
        """Get all user messages."""
        return [
            entry
            for entry in self.entries
            if entry.type == LogEntryType.USER and entry.message
        ]

    @property
    def assistant_messages(self) -> list[ClaudeLogEntry]:
        """Get all assistant messages."""
        return [
            entry
            for entry in self.entries
            if entry.type == LogEntryType.ASSISTANT and entry.message
        ]

    @property
    def system_messages(self) -> list[ClaudeLogEntry]:
        """Get all system messages."""
        return [entry for entry in self.entries if entry.type == LogEntryType.SYSTEM]

    def get_conversation_thread(self) -> list[ClaudeLogEntry]:
        """Get main conversation thread (user/assistant messages only)."""
        return [
            entry
            for entry in self.entries
            if entry.type in [LogEntryType.USER, LogEntryType.ASSISTANT]
            and entry.message is not None
        ]
