#!/usr/bin/env python3
"""Example client for Claude Code log streaming."""

import asyncio
import json
import sys
from datetime import datetime

import websockets


async def stream_claude_logs(uri: str = "ws://localhost:8765") -> None:
    """Connect to Claude Code log streaming server and display logs."""

    print(f"🔗 Connecting to {uri}")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to Claude Code log stream")
            print("📡 Listening for new log entries...\n")

            # Send ping to test connection
            await websocket.send(json.dumps({"type": "ping"}))

            async for message in websocket:
                try:
                    data = json.loads(message)

                    if data["type"] == "pong":
                        print("🏓 Server responded to ping")
                        continue

                    elif data["type"] == "history":
                        print(f"📜 Received {len(data['data'])} historical entries")
                        for entry_data in data["data"][-5:]:  # Show last 5
                            display_log_entry(entry_data)
                        print("─" * 60)
                        continue

                    elif data["type"] == "log_entry":
                        display_log_entry(data["data"])

                except json.JSONDecodeError:
                    print("⚠️  Received invalid JSON from server")
                except KeyError as e:
                    print(f"⚠️  Missing key in message: {e}")
                except Exception as e:
                    print(f"❌ Error processing message: {e}")

    except websockets.exceptions.ConnectionClosed:
        print("❌ Failed to connect. Is the streaming server running?")
        print("   Start it with: python -m clod.streaming")
    except KeyboardInterrupt:
        print("\n👋 Disconnected by user")
    except Exception as e:
        print(f"❌ Connection error: {e}")


def display_log_entry(entry_data: dict) -> None:
    """Display a log entry in a readable format."""

    # Extract basic info
    log_type = entry_data.get("type", "unknown")
    timestamp = entry_data.get("timestamp")
    session_id = entry_data.get("session_id", "unknown")[:8]

    # Format timestamp
    time_str = ""
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            time_str = dt.strftime("%H:%M:%S")
        except Exception:
            time_str = timestamp[:8] if timestamp else ""

    # Get message content
    message = entry_data.get("message", {})
    role = message.get("role", "").upper()
    content = message.get("content", "")

    # Handle different content types
    content_preview = ""
    if isinstance(content, str):
        content_preview = content[:100]
    elif isinstance(content, list) and content:
        # Extract text from content blocks
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    content_preview = block.get("text", "")[:100]
                    break
                elif block.get("type") == "tool_use":
                    tool_name = block.get("name", "unknown")
                    content_preview = f"[Tool: {tool_name}]"
                    break

    # Color coding
    if log_type == "user":
        icon = "👤"
        color = "\033[36m"  # Cyan
    elif log_type == "assistant":
        icon = "🤖"
        color = "\033[32m"  # Green
    elif log_type == "system":
        icon = "⚙️"
        color = "\033[33m"  # Yellow
    else:
        icon = "📝"
        color = "\033[37m"  # White

    reset = "\033[0m"

    # Format output
    if content_preview:
        if role:
            print(f"{color}{icon} [{time_str}] {role} ({session_id}){reset}")
        else:
            print(
                f"{color}{icon} [{time_str}] {log_type.upper()} ({session_id}){reset}"
            )
        print(f"   {content_preview}{'...' if len(str(content)) > 100 else ''}")
    else:
        print(f"{color}{icon} [{time_str}] {log_type.upper()} ({session_id}){reset}")

    print()


async def interactive_client() -> None:
    """Interactive client with menu options."""

    print("🎯 Claude Code Log Stream Client")
    print("=" * 40)
    print("1. Stream logs in real-time")
    print("2. Request recent history")
    print("3. Custom server URI")
    print("q. Quit")

    choice = input("\nSelect option: ").strip().lower()

    if choice == "q":
        return

    uri = "ws://localhost:8765"

    if choice == "3":
        uri = input("Enter WebSocket URI: ").strip()
        if not uri.startswith("ws://") and not uri.startswith("wss://"):
            uri = f"ws://{uri}"

    if choice == "2":
        # Request history only
        try:
            async with websockets.connect(uri) as websocket:
                print("📡 Requesting recent history...")
                await websocket.send(
                    json.dumps({"type": "request_history", "limit": 20})
                )

                message = await websocket.recv()
                data = json.loads(message)

                if data["type"] == "history":
                    print(f"\n📜 Recent History ({len(data['data'])} entries):")
                    print("=" * 50)
                    for entry_data in data["data"]:
                        display_log_entry(entry_data)

        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        # Stream logs
        await stream_claude_logs(uri)


def main() -> None:
    """Main entry point."""

    if len(sys.argv) > 1:
        uri = sys.argv[1]
        asyncio.run(stream_claude_logs(uri))
    else:
        asyncio.run(interactive_client())


if __name__ == "__main__":
    main()
