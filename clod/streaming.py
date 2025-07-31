"""Claude Code log streaming server."""

import asyncio
import json
import logging
from functools import partial
from pathlib import Path
from typing import Any

import websockets
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from websockets.legacy.server import WebSocketServerProtocol

from .log_parser import find_log_files
from .models.claude_log import ClaudeLogEntry

logger = logging.getLogger(__name__)


class ClaudeLogStreamer(FileSystemEventHandler):
    """Streams Claude Code JSONL logs via WebSocket."""

    def __init__(self) -> None:
        self.clients: set[WebSocketServerProtocol] = set()
        self.file_positions: dict[str, int] = {}
        self.observer = Observer()

    async def register_client(self, websocket: WebSocketServerProtocol) -> None:
        """Register a new WebSocket client."""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")

        # Send recent history on connect
        await self.send_recent_history(websocket)

    async def unregister_client(self, websocket: WebSocketServerProtocol) -> None:
        """Unregister a WebSocket client."""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def broadcast_entry(self, entry: ClaudeLogEntry) -> None:
        """Broadcast a log entry to all connected clients."""
        if not self.clients:
            return

        message = {"type": "log_entry", "data": entry.dict(exclude_none=True)}

        # Send to all clients
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.add(client)

        # Clean up disconnected clients
        for client in disconnected:
            self.clients.discard(client)

    def on_modified(self, event: Any) -> None:  # noqa: ANN401
        """Handle file modification events."""
        if not str(event.src_path).endswith(".jsonl"):
            return

        task = asyncio.create_task(self.process_new_entries(Path(str(event.src_path))))
        # Store task reference to avoid RUF006 warning
        self._background_tasks: set[asyncio.Task[None]] = getattr(
            self, "_background_tasks", set()
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def process_new_entries(self, file_path: Path) -> None:
        """Process new entries from a modified JSONL file."""
        file_key = str(file_path)
        last_position = self.file_positions.get(file_key, 0)

        try:
            with file_path.open("r", encoding="utf-8") as f:
                f.seek(last_position)

                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        entry = ClaudeLogEntry(**data)
                        await self.broadcast_entry(entry)
                    except Exception as e:
                        logger.warning(f"Failed to parse entry: {e}")

                # Update file position
                self.file_positions[file_key] = f.tell()

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

    async def send_recent_history(
        self, websocket: WebSocketServerProtocol, limit: int = 50
    ) -> None:
        """Send recent log entries to a newly connected client."""
        try:
            log_files = find_log_files()[:5]  # Recent files
            entries = []

            for log_file in log_files:
                try:
                    with log_file.open("r", encoding="utf-8") as f:
                        lines = f.readlines()
                        for line in lines[-10:]:  # Last 10 entries per file
                            line = line.strip()
                            if line:
                                try:
                                    data = json.loads(line)
                                    entry = ClaudeLogEntry(**data)
                                    entries.append(entry)
                                except Exception:
                                    continue
                except Exception:
                    continue

            # Sort by timestamp and take most recent
            entries.sort(key=lambda e: e.timestamp or "", reverse=True)

            # Send history message
            history_message = {
                "type": "history",
                "data": [entry.dict(exclude_none=True) for entry in entries[:limit]],
            }

            await websocket.send(json.dumps(history_message))

        except Exception as e:
            logger.error(f"Error sending history: {e}")

    def start_watching(self, projects_dir: Path | None = None) -> None:
        """Start watching Claude Code log directories."""
        if projects_dir is None:
            projects_dir = Path.home() / ".claude" / "projects"

        if not projects_dir.exists():
            logger.warning(f"Projects directory not found: {projects_dir}")
            return

        # Initialize file positions for existing files
        for log_file in find_log_files(projects_dir):
            try:
                self.file_positions[str(log_file)] = log_file.stat().st_size
            except Exception:
                self.file_positions[str(log_file)] = 0

        # Start watching
        self.observer.schedule(self, str(projects_dir), recursive=True)
        self.observer.start()
        logger.info(f"Started watching {projects_dir}")

    def stop_watching(self) -> None:
        """Stop watching for file changes."""
        self.observer.stop()
        self.observer.join()


# WebSocket server handler
async def handle_client(
    websocket: WebSocketServerProtocol, path: str, streamer: ClaudeLogStreamer
) -> None:
    """Handle WebSocket client connections."""
    await streamer.register_client(websocket)

    try:
        # Keep connection alive and handle client messages
        async for message in websocket:
            try:
                data = json.loads(message)

                if data.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                elif data.get("type") == "request_history":
                    limit = data.get("limit", 50)
                    await streamer.send_recent_history(websocket, limit)

            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from client")
            except Exception as e:
                logger.error(f"Error handling client message: {e}")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await streamer.unregister_client(websocket)


async def run_streaming_server(host: str = "localhost", port: int = 8765) -> None:
    """Run the Claude Code log streaming server."""
    streamer = ClaudeLogStreamer()
    streamer.start_watching()

    # Create WebSocket server with streamer bound to handler
    handler = partial(handle_client, streamer=streamer)
    server = await websockets.serve(handler, host, port)

    logger.info(f"Claude Code log streaming server started on ws://{host}:{port}")

    try:
        await server.wait_closed()
    finally:
        streamer.stop_watching()


def main() -> None:
    """CLI entry point for streaming server."""
    import argparse

    parser = argparse.ArgumentParser(description="Claude Code log streaming server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run server
    try:
        asyncio.run(run_streaming_server(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")


if __name__ == "__main__":
    main()
