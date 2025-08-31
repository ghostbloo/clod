#!/usr/bin/env python3

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, field_validator


class Account(BaseModel):
    uuid: str

# Citation models
class CitationDetails(BaseModel):
    type: str
    url: str | None = None
    # Add other fields as discovered
    model_config = ConfigDict(extra='forbid')

class Citation(BaseModel):
    uuid: str
    start_index: int
    end_index: int
    details: CitationDetails | None = None
    model_config = ConfigDict(extra='forbid')

# File/Attachment models
class FileReference(BaseModel):
    file_name: str
    # Add other fields as discovered
    model_config = ConfigDict(extra='forbid')

# Tool result content models
class ToolResultTextContent(BaseModel):
    type: Literal["text"]
    text: str
    uuid: str | None = None
    model_config = ConfigDict(extra='forbid')

class ToolResultWebContent(BaseModel):
    type: Literal["web"]
    title: str
    url: str
    metadata: dict[str, Any] | None = None
    is_missing: bool | None = None
    text: str
    is_citable: bool | None = None
    prompt_context_metadata: dict[str, Any] | None = None
    model_config = ConfigDict(extra='forbid')

ToolResultContentItem = Union[ToolResultTextContent, ToolResultWebContent, dict[str, Any]]

# Display content models
class DisplayContent(BaseModel):
    type: str
    content: str | list[dict[str, Any]] | None = None  # Can be string or list of items
    is_trusted: bool | None = None
    link: str | dict[str, Any] | None = None  # Can be string or dict with title/url
    table: dict[str, Any] | list[list[Any]] | None = None  # Can be dict or list of lists
    model_config = ConfigDict(extra='allow')  # Allow extra fields for flexibility

class BaseContentBlock(BaseModel):
    start_timestamp: datetime | None = None
    stop_timestamp: datetime | None = None
    type: str
    model_config = ConfigDict(extra='forbid')

class TextContentBlock(BaseContentBlock):
    type: Literal["text"]
    text: str
    citations: list[Citation] = []

    @field_validator('citations', mode='before')
    @classmethod
    def parse_citations(cls, v):
        if not v:
            return []
        parsed = []
        for cit in v:
            if isinstance(cit, dict):
                # Parse details if present
                if 'details' in cit and isinstance(cit['details'], dict):
                    cit['details'] = CitationDetails(**cit['details'])
                parsed.append(Citation(**cit))
            else:
                parsed.append(cit)
        return parsed

class ThinkingSummary(BaseModel):
    summary: str
    model_config = ConfigDict(extra='forbid')

class ThinkingContentBlock(BaseContentBlock):
    type: Literal["thinking"]
    thinking: str
    summaries: list[str] | None = None  # After validation, always strings
    cut_off: bool | None = None

    @field_validator('summaries', mode='before')
    @classmethod
    def parse_summaries(cls, v):
        if v is None:
            return None
        parsed = []
        for item in v:
            if isinstance(item, str):
                parsed.append(item)
            elif isinstance(item, dict) and 'summary' in item:
                parsed.append(item['summary'])
            else:
                parsed.append(item)
        return parsed

class ToolUseContentBlock(BaseContentBlock):
    type: Literal["tool_use"]
    name: str
    input: dict[str, Any]  # Keep as Any since input varies by tool
    message: str | None = None
    integration_name: str | None = None
    integration_icon_url: str | None = None
    context: dict[str, Any] | None = None  # Usually empty, keep flexible
    display_content: DisplayContent | None = None
    approval_options: list[str] | None = None  # Always a list when present
    approval_key: str | None = None

    @field_validator('approval_options', mode='before')
    @classmethod
    def normalize_approval_options(cls, v):
        # Handle both list and dict formats
        if isinstance(v, dict):
            return list(v.keys()) if v else None
        return v

    @field_validator('display_content', mode='before')
    @classmethod
    def parse_display_content(cls, v):
        if v and isinstance(v, dict):
            return DisplayContent(**v)
        return v

class ToolResultContentBlock(BaseContentBlock):
    type: Literal["tool_result"]
    name: str
    content: list[ToolResultContentItem] | str  # Usually list of content items
    is_error: bool = False
    message: str | None = None
    integration_name: str | None = None
    integration_icon_url: str | None = None
    display_content: DisplayContent | None = None

    @field_validator('content', mode='before')
    @classmethod
    def parse_content(cls, v):
        if isinstance(v, list):
            parsed = []
            for item in v:
                if isinstance(item, dict):
                    item_type = item.get('type')
                    if item_type == 'text':
                        parsed.append(ToolResultTextContent(**item))
                    elif item_type == 'web':
                        parsed.append(ToolResultWebContent(**item))
                    else:
                        parsed.append(item)  # Fallback for unknown types
                else:
                    parsed.append(item)
            return parsed
        return v

    @field_validator('display_content', mode='before')
    @classmethod
    def parse_display_content(cls, v):
        if v and isinstance(v, dict):
            return DisplayContent(**v)
        return v

ContentBlock = Union[TextContentBlock, ThinkingContentBlock, ToolUseContentBlock, ToolResultContentBlock]

class ChatMessage(BaseModel):
    uuid: str
    text: str
    content: list[ContentBlock]
    sender: Literal["human", "assistant"]
    created_at: datetime
    updated_at: datetime
    attachments: list[dict[str, Any]] = []  # Rarely used, keep flexible
    files: list[FileReference] = []
    model_config = ConfigDict(extra='forbid')

    @field_validator('files', mode='before')
    @classmethod
    def parse_files(cls, v):
        if not v:
            return []
        parsed = []
        for f in v:
            if isinstance(f, dict):
                parsed.append(FileReference(**f))
            else:
                parsed.append(f)
        return parsed

    @field_validator('content', mode='before')
    @classmethod
    def parse_content_blocks(cls, v):
        if not isinstance(v, list):
            return v

        parsed_blocks = []
        for block in v:
            if not isinstance(block, dict):
                parsed_blocks.append(block)
                continue

            block_type = block.get('type')
            if block_type == 'text':
                parsed_blocks.append(TextContentBlock(**block))
            elif block_type == 'thinking':
                parsed_blocks.append(ThinkingContentBlock(**block))
            elif block_type == 'tool_use':
                parsed_blocks.append(ToolUseContentBlock(**block))
            elif block_type == 'tool_result':
                parsed_blocks.append(ToolResultContentBlock(**block))
            else:
                # Fallback for unknown types
                parsed_blocks.append(BaseContentBlock(**block))

        return parsed_blocks

class Conversation(BaseModel):
    uuid: str
    name: str
    created_at: datetime
    updated_at: datetime
    account: Account
    chat_messages: list[ChatMessage]
    model_config = ConfigDict(extra='forbid')

    @property
    def message_count(self) -> int:
        return len(self.chat_messages)

    @property
    def human_messages(self) -> list[ChatMessage]:
        return [msg for msg in self.chat_messages if msg.sender == "human"]

    @property
    def assistant_messages(self) -> list[ChatMessage]:
        return [msg for msg in self.chat_messages if msg.sender == "assistant"]

    @property
    def duration_days(self) -> float:
        return (self.updated_at - self.created_at).total_seconds() / (24 * 3600)

def main() -> list[Conversation]:
    # Load and parse the conversation data
    data_path = Path("/Users/me/code/ai/clod/conversations.json")

    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    print("Loading conversation data...")
    with open(data_path) as f:
        raw_data = json.load(f)

    print("Parsing conversations...")
    conversations = []
    for i, conv_data in enumerate(raw_data):
        try:
            conv = Conversation.model_validate(conv_data)
            conversations.append(conv)
        except Exception as e:
            print(f"Failed to parse conversation {i}: {e}")
            continue

    print(f"Successfully parsed {len(conversations)} conversations")

    return conversations


if __name__ == "__main__":
    conversations = main()

    # Print some statistics
    print("\nConversation Statistics:")
    print(f"Total conversations: {len(conversations)}")

    if conversations:
        total_messages = sum(c.message_count for c in conversations)
        print(f"Total messages: {total_messages}")

        # Count content block types
        block_types = Counter()
        for conv in conversations:
            for msg in conv.chat_messages:
                for block in msg.content:
                    block_types[block.type] += 1

        print("\nContent block type distribution:")
        for block_type, count in block_types.most_common():
            print(f"  - {block_type}: {count}")

        # Show sample conversation
        print(f"\nFirst conversation: {conversations[0].name}")
        print(f"  Messages: {conversations[0].message_count}")
        print(f"  Duration: {conversations[0].duration_days:.1f} days")
