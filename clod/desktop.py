"""Claude Desktop chat history parser."""

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ChatMessage:
    """Represents a chat message from Claude Desktop."""
    conversation_id: str
    text: str
    timestamp: datetime | None = None
    message_type: str = "user"  # user or assistant
    is_draft: bool = False


@dataclass
class Conversation:
    """Represents a conversation thread."""
    id: str
    messages: list[ChatMessage]
    last_activity: datetime | None = None


class ClaudeDesktopParser:
    """Parser for Claude Desktop chat history stored in LevelDB."""

    def __init__(self) -> None:
        self.claude_dir = Path.home() / "Library/Application Support/Claude"
        self.leveldb_dir = self.claude_dir / "Local Storage/leveldb"

    def _run_strings(self, file_path: Path) -> list[str]:
        """Extract strings from a binary file."""
        try:
            result = subprocess.run(
                ["strings", str(file_path)],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.split('\n')
        except subprocess.CalledProcessError:
            return []

    def _extract_messages_from_file(self, file_path: Path) -> list[ChatMessage]:
        """Extract chat messages from a single LevelDB file."""
        lines = self._run_strings(file_path)
        messages = []

        for i, line in enumerate(lines):
            line = line.strip()

            # Look for Local Storage keys that contain textInput (user drafts)
            if line.startswith('LSS-') and 'textInput' in line:
                conversation_id = line.split(':')[0].replace('LSS-', '')

                # The next few lines should contain the JSON data - collect them
                json_parts = []
                j = i + 1
                while j < len(lines) and j < i + 10:  # Look ahead up to 10 lines
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith('LSS-'):
                        json_parts.append(next_line)
                    else:
                        break
                    j += 1

                if json_parts:
                    # Try to reconstruct the JSON
                    potential_json = ''.join(json_parts)

                    # Find complete JSON by counting braces
                    if potential_json.startswith('{"type":"doc"'):
                        brace_count = 0
                        json_end = 0
                        for idx, char in enumerate(potential_json):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = idx + 1
                                    break

                        if json_end > 0:
                            json_str = potential_json[:json_end]
                            try:
                                data = json.loads(json_str)
                                text = self._extract_text_from_doc(data)
                                if text and len(text) > 3:  # Filter out very short messages
                                    messages.append(ChatMessage(
                                        conversation_id=conversation_id,
                                        text=text,
                                        is_draft=True
                                    ))
                            except json.JSONDecodeError:
                                # For debugging - try a simpler approach
                                pass

            # Also look for text messages in general JSON format (fallback method)
            match = re.search(r'"text":"([^"]+)"', line)
            if match:
                text = match.group(1)
                if len(text) > 10:  # Only longer messages
                    # Try to guess conversation from surrounding context
                    conv_id = "unknown"
                    messages.append(ChatMessage(
                        conversation_id=conv_id,
                        text=text
                    ))

        return messages

    def _extract_text_from_doc(self, doc_data: dict) -> str:
        """Extract text content from Claude's document format."""
        text_parts = []

        def extract_recursive(node: Any) -> None:
            if isinstance(node, dict):
                if node.get('type') == 'text':
                    text_parts.append(node.get('text', ''))
                elif 'content' in node:
                    content = node['content']
                    if isinstance(content, list):
                        for item in content:
                            extract_recursive(item)
                    else:
                        extract_recursive(content)
            elif isinstance(node, list):
                for item in node:
                    extract_recursive(item)

        extract_recursive(doc_data)
        return ' '.join(text_parts).strip()

    def get_all_messages(self) -> list[ChatMessage]:
        """Extract all messages from all LevelDB files."""
        if not self.leveldb_dir.exists():
            return []

        all_messages = []

        # Process all .ldb and .log files
        for pattern in ['*.ldb', '*.log']:
            for file_path in self.leveldb_dir.glob(pattern):
                messages = self._extract_messages_from_file(file_path)
                all_messages.extend(messages)

        # Remove duplicates while preserving order
        seen = set()
        unique_messages = []
        for msg in all_messages:
            msg_key = (msg.conversation_id, msg.text)
            if msg_key not in seen:
                seen.add(msg_key)
                unique_messages.append(msg)

        return unique_messages

    def get_conversations(self) -> dict[str, Conversation]:
        """Group messages by conversation."""
        messages = self.get_all_messages()
        conversations = {}

        for msg in messages:
            conv_id = msg.conversation_id
            if conv_id not in conversations:
                conversations[conv_id] = Conversation(id=conv_id, messages=[])
            conversations[conv_id].messages.append(msg)

        return conversations

    def search_messages(self, query: str, case_sensitive: bool = False) -> list[ChatMessage]:
        """Search for messages containing the query."""
        messages = self.get_all_messages()
        results = []

        search_query = query if case_sensitive else query.lower()

        for msg in messages:
            search_text = msg.text if case_sensitive else msg.text.lower()
            if search_query in search_text:
                results.append(msg)

        return results

    def get_recent_messages(self, limit: int = 20) -> list[ChatMessage]:
        """Get the most recent messages (approximate ordering)."""
        messages = self.get_all_messages()
        # Since we don't have timestamps, just return the last N messages
        return messages[-limit:] if len(messages) > limit else messages
