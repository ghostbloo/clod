"""CLI interface for clod utilities."""

import json
from pathlib import Path

import click

from .config_models import ClaudeCodeSettings
from .desktop_mcp import ClaudeDesktopMcpManager
from .hooks import HookManager
from .log_parser import find_log_files, get_recent_sessions
from .sfx import SoundEffectsManager, run_tui
from .sound_packs import SoundPackManager
from .tmux import TmuxController


@click.group()
@click.version_option()
def main() -> None:
    """Claude Code utilities and hacks."""
    pass


@main.command(
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],  # Disable Click's help handling
    }
)
@click.option(
    "--safe",
    is_flag=True,
    help="Run claude without --dangerously-skip-permissions",
)
@click.pass_context
def code(ctx: click.Context, safe: bool) -> None:
    """Alias for 'claude --dangerously-skip-permissions'."""
    import os
    import shutil
    import sys
    from pathlib import Path

    # Try to find claude executable in various locations
    claude_path = None

    # Check if claude is in PATH (excluding shell aliases)
    claude_path = shutil.which("claude")

    # If not found in PATH, check common Claude Code installation locations
    if not claude_path:
        possible_paths = [
            Path.home() / ".claude" / "local" / "claude",
            Path.home() / ".claude" / "local" / "node_modules" / ".bin" / "claude",
        ]

        for path in possible_paths:
            if path.exists() and path.is_file():
                claude_path = str(path)
                break

    if not claude_path:
        click.echo(
            "Error: claude command not found. "
            "Please ensure Claude Code CLI is installed.",
            err=True,
        )
        sys.exit(1)

    cmd = [claude_path]
    if not safe:
        cmd.append("--dangerously-skip-permissions")
    cmd.extend(ctx.args)
    os.execvp(claude_path, cmd)


@main.group()
def tmux() -> None:
    """Tmux workspace management commands."""
    pass


@main.group()
def hooks() -> None:
    """Claude Code hook management commands."""
    pass


@main.group()
def desktop() -> None:
    """Claude Desktop integration commands (MCP server management)."""
    pass


@main.group()
def sfx() -> None:
    """Sound effects management commands."""
    pass




@main.group()
def lint() -> None:
    """Linting and validation commands."""
    pass


@main.group()
def logs() -> None:
    """Claude Code log streaming and analysis commands."""
    pass


@tmux.command()
@click.option("--session", "-s", default="claude-workspace", help="Session name")
@click.option(
    "--working-dir",
    "-C",
    type=click.Path(exists=True, path_type=Path),
    help="Working directory",
)
def setup(session: str, working_dir: Path | None) -> None:
    """Set up Claude tmux workspace."""
    controller = TmuxController(session)
    controller.setup(working_dir)


@tmux.command()
@click.argument("command")
@click.option("--session", "-s", default="claude-workspace", help="Session name")
def send(command: str, session: str) -> None:
    """Send command to Claude pane."""
    controller = TmuxController(session)
    controller.send_keys(command)


@tmux.command()
@click.option("--lines", "-n", default=20, help="Number of lines to read")
@click.option("--session", "-s", default="claude-workspace", help="Session name")
def read(lines: int, session: str) -> None:
    """Read output from Claude pane."""
    controller = TmuxController(session)
    output = controller.read_output(lines)
    if output:
        click.echo(output)


@tmux.command()
@click.option("--session", "-s", default="claude-workspace", help="Session name")
def status(session: str) -> None:
    """Check Claude session status."""
    controller = TmuxController(session)
    status_info = controller.status()

    if status_info["exists"]:
        click.echo(f"✓ Claude session '{status_info['session_name']}' is running")
        click.echo(f"  Panes: {status_info['panes']}")
        click.echo(f"  Windows: {status_info['windows']}")
    else:
        click.echo("✗ Claude session not found")


@tmux.command()
@click.option("--session", "-s", default="claude-workspace", help="Session name")
def kill(session: str) -> None:
    """Kill Claude session."""
    controller = TmuxController(session)
    controller.kill_session()


# REPL-specific commands
@tmux.command()
@click.argument("command")
@click.option("--session", "-s", default="claude-repl", help="Session name")
@click.option(
    "--working-dir",
    "-C",
    type=click.Path(exists=True, path_type=Path),
    help="Working directory",
)
def start_repl(command: str, session: str, working_dir: Path | None) -> None:
    """Start a REPL session with the specified command."""
    controller = TmuxController(session)
    controller.start_repl(command, working_dir)


@tmux.command()
@click.argument("text")
@click.option("--session", "-s", default="claude-repl", help="Session name")
def send_input(text: str, session: str) -> None:
    """Send text input without pressing Enter."""
    controller = TmuxController(session)
    if controller.send_input(text):
        click.echo(f"Sent input: {text}")


@tmux.command()
@click.option(
    "--mode",
    "-m",
    default="standard",
    type=click.Choice(["standard", "vim"]),
    help="Submission mode",
)
@click.option("--session", "-s", default="claude-repl", help="Session name")
def submit(mode: str, session: str) -> None:
    """Submit current input with different submission modes."""
    controller = TmuxController(session)
    if controller.submit(mode):
        click.echo(f"Submitted using {mode} mode")


@tmux.command()
@click.option("--lines", "-n", default=20, help="Number of lines to show")
@click.option("--history", "-H", default=0, help="Number of history lines to include")
@click.option("--session", "-s", default="claude-repl", help="Session name")
def view_output(lines: int, history: int, session: str) -> None:
    """View current REPL output."""
    controller = TmuxController(session)
    output = controller.read_output_with_history(lines, history)
    if output:
        click.echo(output)


@tmux.command()
@click.argument("keys", nargs=-1, required=True)
@click.option("--session", "-s", default="claude-repl", help="Session name")
def send_keys(keys: tuple[str, ...], session: str) -> None:
    """Send raw key combinations (e.g., 'C-c', 'C-d', 'Escape')."""
    controller = TmuxController(session)
    if controller.send_raw_keys(*keys):
        click.echo(f"Sent keys: {' '.join(keys)}")


@tmux.command()
@click.option("--session", "-s", default="claude-repl", help="Session name")
def stop_repl(session: str) -> None:
    """Stop REPL session."""
    controller = TmuxController(session)
    controller.kill_session()


# Hook management commands
@hooks.command()
@click.option(
    "--scope",
    "-s",
    type=click.Choice(["user", "project", "local"]),
    help="Configuration scope",
)
def list(scope: str | None) -> None:
    """List all configured hooks."""
    manager = HookManager(scope=scope)
    hooks = manager.list_hooks()

    if not hooks:
        scope_info = f" ({scope} scope)" if scope else ""
        click.echo(f"No hooks configured{scope_info}.")
        return

    scope_info = f" ({scope} scope)" if scope else ""
    click.echo(f"Configured hooks{scope_info}:")
    for i, hook in enumerate(hooks):
        click.echo(
            f"{i:2d}. {hook['event']:<20} {hook['matcher']:<15} {hook['command']}"
        )


@hooks.command()
@click.argument("hook_type", type=click.Choice(HookManager.HOOK_TYPES))
@click.option("--matcher", "-m", default="*", help="Tool pattern to match")
@click.option("--command", "-c", help="Shell command to execute")
@click.option("--script", "-f", help="Path to existing script")
@click.option("--template", "-t", is_flag=True, help="Create cchooks Python template")
@click.option("--name", "-n", help="Hook name (for templates)")
@click.option(
    "--scope",
    "-s",
    type=click.Choice(["user", "project", "local"]),
    help="Configuration scope",
)
def add(
    hook_type: str,
    matcher: str,
    command: str | None,
    script: str | None,
    template: bool,
    name: str | None,
    scope: str | None,
) -> None:
    """Add a new hook."""
    manager = HookManager(scope=scope)

    try:
        result = manager.add_hook(
            hook_type=hook_type,
            matcher=matcher,
            command=command,
            script_path=script,
            template=template,
            name=name,
        )

        if template:
            click.echo(f"✓ Created template hook: {result}")
        else:
            click.echo(f"✓ Added hook: {result}")

    except ValueError as e:
        click.echo(f"✗ Error: {e}", err=True)


@hooks.command()
@click.argument("identifier")
@click.option(
    "--scope",
    "-s",
    type=click.Choice(["user", "project", "local"]),
    help="Configuration scope",
)
def remove(identifier: str, scope: str | None) -> None:
    """Remove a hook by index."""
    manager = HookManager(scope=scope)

    if manager.remove_hook(identifier):
        click.echo(f"✓ Removed hook: {identifier}")
    else:
        click.echo(f"✗ Hook not found: {identifier}", err=True)


@hooks.command()
@click.argument("identifier")
@click.option("--input", "-i", help="Test input data (JSON)")
@click.option("--dry-run", "-d", is_flag=True, help="Show what would happen")
@click.option(
    "--scope",
    "-s",
    type=click.Choice(["user", "project", "local"]),
    help="Configuration scope",
)
def run(identifier: str, input: str | None, dry_run: bool, scope: str | None) -> None:
    """Run/test a hook."""
    manager = HookManager(scope=scope)
    manager.run_hook(identifier, input, dry_run)


@hooks.command()
@click.argument("identifier")
@click.option(
    "--scope",
    "-s",
    type=click.Choice(["user", "project", "local"]),
    help="Configuration scope",
)
def edit(identifier: str, scope: str | None) -> None:
    """Edit a hook script."""
    import os
    import subprocess

    manager = HookManager(scope=scope)
    hooks = manager.list_hooks()

    try:
        index = int(identifier)
        if 0 <= index < len(hooks):
            hook = hooks[index]
            command = hook["command"]

            # Extract script path from command if it's a Python script
            if command.startswith("python "):
                script_path = command.split(" ", 1)[1]
                if Path(script_path).exists():
                    editor = os.environ.get("EDITOR", "nano")
                    subprocess.run([editor, script_path])
                    return

            click.echo("Hook is not a script file or script not found.")
        else:
            click.echo(f"Invalid hook index: {identifier}")
    except ValueError:
        click.echo(f"Invalid hook identifier: {identifier}")


@desktop.group()
def mcp() -> None:
    """MCP server management commands."""
    pass


@mcp.command(
    "tail",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
)
@click.argument("server_name")
@click.pass_context
def mcp_tail(ctx: click.Context, server_name: str) -> None:
    """Tail logs for an MCP server."""
    import os
    import sys

    # Get log directory from environment variable or use default
    log_dir_str = os.environ.get("CLAUDE_DESKTOP_LOG_DIR", "~/Library/Logs/Claude/")
    log_dir = Path(log_dir_str).expanduser()
    log_file = log_dir / f"mcp-server-{server_name}.log"

    # Build tail command with all extra args
    tail_cmd = ["tail", *ctx.args, str(log_file)]

    # Execute tail directly, replacing the current process
    try:
        os.execvp("tail", tail_cmd)
    except FileNotFoundError:
        click.echo("Error: 'tail' command not found", err=True)
        sys.exit(1)


@mcp.command("logs")
@click.argument("server_name")
@click.option("--lines", "-n", default=50, help="Number of recent log lines to show")
def mcp_logs(server_name: str, lines: int) -> None:
    """Show recent logs from an MCP server."""
    import os

    log_dir_str = os.environ.get("CLAUDE_DESKTOP_LOG_DIR", "~/Library/Logs/Claude/")
    log_dir = Path(log_dir_str).expanduser()
    log_file = log_dir / f"mcp-server-{server_name}.log"

    if not log_file.exists():
        click.echo(f"Log file not found: {log_file}")
        return

    try:
        with log_file.open() as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            for line in recent_lines:
                click.echo(line.rstrip())
    except OSError as e:
        click.echo(f"Error reading log file: {e}")


@mcp.command("list")
def list_servers() -> None:
    """List MCP servers configured in Claude Desktop."""
    import json

    config_path = (
        Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    )

    if not config_path.exists():
        click.echo("Claude Desktop config not found")
        return

    try:
        with config_path.open() as f:
            config = json.load(f)

        mcp_servers = config.get("mcpServers", {})
        if not mcp_servers:
            click.echo("No MCP servers configured")
            return

        click.echo(f"Found {len(mcp_servers)} MCP server(s):")
        for name, server_config in mcp_servers.items():
            command = server_config.get("command", "N/A")
            args = server_config.get("args", [])
            env = server_config.get("env", {})

            click.echo(f"  {name}:")
            click.echo(f"    Command: {command}")
            if args:
                click.echo(f"    Args: {' '.join(args)}")
            if env:
                click.echo(f"    Env: {', '.join(f'{k}={v}' for k, v in env.items())}")

    except (OSError, json.JSONDecodeError) as e:
        click.echo(f"Error reading Claude Desktop config: {e}")


@mcp.command("status")
def mcp_status() -> None:
    """Check status of MCP server logs."""
    import os
    from datetime import datetime

    log_dir_str = os.environ.get("CLAUDE_DESKTOP_LOG_DIR", "~/Library/Logs/Claude/")
    log_dir = Path(log_dir_str).expanduser()

    if not log_dir.exists():
        click.echo(f"Log directory not found: {log_dir}")
        return

    mcp_logs = [f for f in log_dir.glob("mcp-server-*.log")]

    if not mcp_logs:
        click.echo("No MCP server log files found")
        return

    click.echo(f"Found {len(mcp_logs)} MCP server log file(s):")
    for log_file in sorted(mcp_logs):
        server_name = log_file.stem.replace("mcp-server-", "")
        try:
            stat = log_file.stat()
            size = stat.st_size
            modified = datetime.fromtimestamp(stat.st_mtime)

            # Check if log has recent activity (within last hour)
            import time

            recent = (time.time() - stat.st_mtime) < 3600
            status_indicator = "🟢" if recent else "🔴"

            click.echo(
                f"  {status_indicator} {server_name}: {size} bytes, "
                f"modified {modified.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except OSError:
            click.echo(f"  ❓ {server_name}: Unable to read file stats")


# MCP server management commands
@mcp.command("add")
@click.argument("name")
@click.argument("command")
@click.argument("args", nargs=-1)
@click.option("--env", "-e", multiple=True, help="Environment variable (KEY=VALUE)")
def mcp_add(
    name: str, command: str, args: tuple[str, ...], env: tuple[str, ...]
) -> None:
    """Add an MCP server to Claude Desktop config."""
    manager = ClaudeDesktopMcpManager()

    # Parse environment variables
    env_dict = {}
    for env_var in env:
        if "=" in env_var:
            key, value = env_var.split("=", 1)
            env_dict[key] = value
        else:
            click.echo(
                f"Invalid environment variable format: {env_var} (use KEY=VALUE)",
                err=True,
            )
            return

    try:
        manager.add_server(name, command, list(args), env_dict)
        click.echo(f"✓ Added MCP server: {name}")
        click.echo(f"  Command: {command}")
        if args:
            click.echo(f"  Args: {' '.join(args)}")
        if env_dict:
            click.echo(
                f"  Environment: {', '.join(f'{k}={v}' for k, v in env_dict.items())}"
            )
    except Exception as e:
        click.echo(f"✗ Error adding server: {e}", err=True)


@mcp.command("remove")
@click.argument("name")
def mcp_remove(name: str) -> None:
    """Remove an MCP server from Claude Desktop config."""
    manager = ClaudeDesktopMcpManager()

    if manager.remove_server(name):
        click.echo(f"✓ Removed MCP server: {name}")
    else:
        click.echo(f"✗ MCP server not found: {name}", err=True)


@mcp.command("get")
@click.argument("name")
def mcp_get(name: str) -> None:
    """Get details about an MCP server."""
    manager = ClaudeDesktopMcpManager()

    server = manager.get_server(name)
    if not server:
        click.echo(f"✗ MCP server not found: {name}", err=True)
        return

    click.echo(f"{name}:")
    server_type = server.get("type", "stdio")
    click.echo(f"  Type: {server_type}")

    if server_type == "stdio":
        # For stdio servers, we know the structure
        command = server.get("command")
        if command:
            click.echo(f"  Command: {command}")

        args_raw = server.get("args")
        if args_raw:
            try:
                args = list(args_raw)
                click.echo(f"  Args: {' '.join(args)}")
            except (TypeError, ValueError):
                pass

        env_raw = server.get("env")
        if env_raw:
            try:
                env = dict(env_raw)  # type: ignore
                click.echo("  Environment:")
                for key, value in env.items():
                    click.echo(f"    {key}={value}")
            except (TypeError, ValueError):
                pass

    elif server_type in ("sse", "http"):
        # For SSE/HTTP servers, we know the structure
        url = server.get("url")
        if url:
            click.echo(f"  URL: {url}")

        headers_raw = server.get("headers")
        if headers_raw:
            try:
                headers = dict(headers_raw)  # type: ignore
                click.echo("  Headers:")
                for key, value in headers.items():
                    click.echo(f"    {key}: {value}")
            except (TypeError, ValueError):
                pass


@mcp.command("enable")
@click.argument("name")
def mcp_enable(name: str) -> None:
    """Enable a disabled MCP server."""
    manager = ClaudeDesktopMcpManager()

    if manager.enable_server(name):
        click.echo(f"✓ Enabled MCP server: {name}")
    else:
        click.echo(f"✗ MCP server not found in disabled servers: {name}", err=True)


@mcp.command("disable")
@click.argument("name")
def mcp_disable(name: str) -> None:
    """Disable an MCP server."""
    manager = ClaudeDesktopMcpManager()

    if manager.disable_server(name):
        click.echo(f"✓ Disabled MCP server: {name}")
    else:
        click.echo(f"✗ MCP server not found: {name}", err=True)


# Sound effects management commands
@sfx.command()
def tui() -> None:
    """Open interactive TUI for configuring sound effects."""
    run_tui()


@sfx.command("list")
def list_sfx() -> None:
    """List current sound effect mappings."""
    manager = SoundEffectsManager()
    mappings = manager.get_current_mappings()

    if not mappings:
        click.echo("No sound effects configured.")
        return

    click.echo("Current sound effect mappings:")
    for _key, mapping in mappings.items():
        hook_type = mapping["hook_type"]
        matcher = mapping["matcher"] or "(empty)"
        sound = mapping["sound"]
        click.echo(f"  {hook_type} | {matcher} -> {sound}")


@sfx.command()
@click.argument("hook_type", type=click.Choice(SoundEffectsManager.HOOK_TYPES))
@click.argument("matcher", default="*")
@click.argument("sound_file")
def set(hook_type: str, matcher: str, sound_file: str) -> None:
    """Set sound effect for a hook type and matcher."""
    manager = SoundEffectsManager()

    if manager.set_sound_mapping(hook_type, matcher, sound_file):
        click.echo(f"✓ Set {sound_file} for {hook_type} | {matcher}")
    else:
        click.echo(
            f"✗ Failed to set sound effect. "
            f"Check that {sound_file} exists in ~/.claude/sounds/"
        )


@sfx.command("remove")
@click.argument("hook_type", type=click.Choice(SoundEffectsManager.HOOK_TYPES))
@click.argument("matcher", default="*")
def remove_sfx(hook_type: str, matcher: str) -> None:
    """Remove sound effect for a hook type and matcher."""
    manager = SoundEffectsManager()

    if manager.remove_sound_mapping(hook_type, matcher):
        click.echo(f"✓ Removed sound effect for {hook_type} | {matcher}")
    else:
        click.echo(f"✗ No sound effect found for {hook_type} | {matcher}")


@sfx.command()
@click.argument("sound_file")
def play(sound_file: str) -> None:
    """Play a sound file for testing."""
    from .sfx import SoundPlayer

    manager = SoundEffectsManager()
    sound_path = manager.sounds_path / sound_file

    if not sound_path.exists():
        click.echo(f"✗ Sound file not found: {sound_file}")
        return

    player = SoundPlayer()
    if player.play(sound_path):
        click.echo(f"♪ Playing {sound_file}")
    else:
        click.echo(f"✗ Failed to play {sound_file}")


@sfx.command()
def sounds() -> None:
    """List available sound files."""
    manager = SoundEffectsManager()
    sound_files = manager.get_sound_files()

    if not sound_files:
        click.echo("No sound files found in ~/.claude/sounds/")
        return

    click.echo(f"Available sound files ({len(sound_files)}):")
    for sound_path in sound_files:
        click.echo(f"  {sound_path.name}")


# Lint commands
@lint.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.option(
    "--stdin", "-", "use_stdin", is_flag=True, help="Read settings from stdin"
)
def settings(file_path: str | None, use_stdin: bool) -> None:
    """Validate a Claude Code settings.json file."""
    import json
    import sys

    from pydantic import ValidationError

    # Get JSON content
    content = None
    source = "stdin"

    if use_stdin:
        try:
            content = sys.stdin.read()
        except KeyboardInterrupt:
            click.echo("\nOperation cancelled.", err=True)
            sys.exit(1)
    elif file_path:
        source = file_path
        try:
            with Path(file_path).open() as f:
                content = f.read()
        except OSError as e:
            click.echo(f"Error reading file: {e}", err=True)
            sys.exit(1)
    else:
        # Try to find settings.json in common locations
        possible_paths = [
            Path.cwd() / ".claude" / "settings.json",
            Path.cwd() / ".claude" / "settings.local.json",
            Path.home() / ".claude" / "settings.json",
        ]

        for path in possible_paths:
            if path.exists():
                file_path = str(path)
                source = file_path
                try:
                    with path.open() as f:
                        content = f.read()
                    break
                except OSError as e:
                    click.echo(f"Error reading {path}: {e}", err=True)
                    continue

        if not content:
            click.echo(
                "No settings file found. Specify a file path or use --stdin.",
                err=True,
            )
            sys.exit(1)

    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON in {source}: {e}", err=True)
        sys.exit(1)

    # Validate with Pydantic model
    try:
        settings = ClaudeCodeSettings(**data)
        click.echo(f"✓ Valid Claude Code settings ({source})")

        # Show summary of configured features
        features = []
        if settings.model:
            features.append(f"model: {settings.model}")
        if settings.permissions:
            features.append("permissions configured")
        if settings.hooks:
            features.append(f"hooks: {', '.join(settings.hooks.keys())}")
        if settings.env:
            features.append(f"env vars: {len(settings.env)}")
        if settings.api_key_helper:
            features.append("API key helper")

        if features:
            click.echo("  Configured: " + ", ".join(features))

    except ValidationError as e:
        click.echo(f"✗ Invalid Claude Code settings ({source}):", err=True)
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            click.echo(f"  - {loc}: {msg}", err=True)
        sys.exit(1)


# Log streaming and analysis commands
@logs.command("stream")
@click.option("--host", default="localhost", help="Host to bind server to")
@click.option("--port", type=int, default=8765, help="Port to bind server to")
@click.option("--debug", is_flag=True, help="Enable debug logging")
def stream_logs(host: str, port: int, debug: bool) -> None:
    """Start Claude Code log streaming server."""
    import asyncio
    import logging

    from .streaming import run_streaming_server

    # Configure logging
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    click.echo(f"🚀 Starting Claude Code log streaming server on ws://{host}:{port}")

    try:
        asyncio.run(run_streaming_server(host, port))
    except KeyboardInterrupt:
        click.echo("\n👋 Server stopped by user")


@logs.command("recent")
@click.option("--limit", "-n", default=5, help="Number of recent sessions to show")
@click.option(
    "--detailed", "-d", is_flag=True, help="Show detailed session information"
)
def recent_logs(limit: int, detailed: bool) -> None:
    """Show recent Claude Code sessions."""
    try:
        sessions = get_recent_sessions(limit)

        if not sessions:
            click.echo("No Claude Code sessions found.")
            return

        click.echo(f"📊 {len(sessions)} recent Claude Code sessions:")
        click.echo()

        for i, session in enumerate(sessions, 1):
            duration_str = ""
            if session.start_time and session.end_time:
                duration = session.end_time - session.start_time
                duration_str = f" (Duration: {duration})"

            click.echo(f"{i}. Session {session.session_id[:8]}...{duration_str}")

            if session.start_time:
                click.echo(f"   📅 Started: {session.start_time}")

            conversation = session.get_conversation_thread()
            click.echo(
                f"   💬 Messages: {len(session.user_messages)} user, "
                f"{len(session.assistant_messages)} assistant"
            )

            if detailed and conversation:
                # Show first few exchanges
                click.echo("   📝 Recent conversation:")
                for entry in conversation[:3]:
                    if entry.message is None:
                        continue
                    role = entry.message.role.upper()
                    content = ""

                    if isinstance(entry.message.content, str):
                        content = entry.message.content[:60]
                    elif hasattr(entry.message, "content") and hasattr(
                        entry.message.content, "__iter__"
                    ):
                        for block in entry.message.content:
                            if hasattr(block, "text"):
                                content = block.text[:60]
                                break
                            elif hasattr(block, "name"):
                                content = f"[Tool: {block.name}]"
                                break

                    click.echo(f"      {role}: {content}...")

            click.echo()

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)


@logs.command("stats")
def log_stats() -> None:
    """Show Claude Code log statistics."""
    try:
        log_files = find_log_files()
        sessions = get_recent_sessions(limit=50)  # Analyze more sessions for stats

        if not sessions:
            click.echo("No Claude Code sessions found.")
            return

        # Calculate statistics
        total_entries = sum(len(s.entries) for s in sessions)
        total_user_msgs = sum(len(s.user_messages) for s in sessions)
        total_assistant_msgs = sum(len(s.assistant_messages) for s in sessions)

        # Count tool usage
        tool_uses = 0
        tools_used = set()

        for session in sessions:
            for entry in session.entries:
                if (
                    entry.message
                    and hasattr(entry.message, "content")
                    and hasattr(entry.message.content, "__iter__")
                    and not isinstance(entry.message.content, str)
                ):
                    for block in entry.message.content:
                        if hasattr(block, "name"):  # ToolUseContentBlock
                            tool_uses += 1
                            tools_used.add(block.name)

        # Find most active session
        most_active = (
            max(sessions, key=lambda s: len(s.get_conversation_thread()))
            if sessions
            else None
        )

        click.echo("📊 Claude Code Log Statistics")
        click.echo("=" * 35)
        click.echo(f"📁 Total log files: {len(log_files)}")
        click.echo(f"📋 Analyzed sessions: {len(sessions)}")
        click.echo(f"📝 Total log entries: {total_entries}")
        click.echo(f"👤 User messages: {total_user_msgs}")
        click.echo(f"🤖 Assistant messages: {total_assistant_msgs}")
        click.echo(f"🛠️  Tool executions: {tool_uses}")

        if tools_used:
            click.echo(f"🔧 Unique tools used: {', '.join(sorted(tools_used))}")

        if most_active:
            active_count = len(most_active.get_conversation_thread())
            click.echo(
                f"🏆 Most active session: {most_active.session_id[:8]}... "
                f"({active_count} messages)"
            )

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)


@logs.command("client")
@click.argument("uri", default="ws://localhost:8765")
def log_client(uri: str) -> None:
    """Connect to Claude Code log streaming server."""
    import subprocess
    import sys
    from pathlib import Path

    # Run the example client
    client_path = Path(__file__).parent.parent / "examples" / "streaming_client.py"

    if not client_path.exists():
        click.echo(
            "❌ Streaming client not found. Install examples manually.", err=True
        )
        return

    try:
        subprocess.run([sys.executable, str(client_path), uri])
    except KeyboardInterrupt:
        click.echo("\n👋 Client stopped by user")


# Sound pack management commands
@sfx.command("install")
@click.argument("pack_path", type=click.Path(exists=True, path_type=Path))
@click.option("--name", "-n", help="Override pack name")
def install_pack(pack_path: Path, name: str | None) -> None:
    """Install a sound pack from zip or directory."""
    manager = SoundPackManager()
    
    try:
        success = manager.install_pack(pack_path, name)
        if success:
            final_name = name or pack_path.stem
            click.echo(f"✓ Installed sound pack: {final_name}")
        else:
            click.echo("✗ Failed to install sound pack", err=True)
    except Exception as e:
        click.echo(f"✗ Error installing pack: {e}", err=True)


@sfx.command("list-packs")
def list_packs() -> None:
    """List all installed sound packs."""
    manager = SoundPackManager()
    packs = manager.list_installed_packs()
    
    if not packs:
        click.echo("No sound packs installed.")
        return
    
    click.echo(f"Installed sound packs ({len(packs)}):")
    for pack in packs:
        click.echo(f"  {pack['name']} v{pack['version']}")
        if pack['description']:
            click.echo(f"    {pack['description']}")
        if pack['author']:
            click.echo(f"    Author: {pack['author']}")
        click.echo(f"    Location: {pack['pack_dir']}")
        click.echo()


@sfx.command("enable-claude")
@click.argument("pack_name")
@click.option("--matcher", "-m", default="*", help="Tool pattern to match")
def enable_claude(pack_name: str, matcher: str) -> None:
    """Enable sound pack for Claude Code."""
    manager = SoundPackManager()
    
    if manager.enable_for_claude_code(pack_name, matcher):
        click.echo(f"✓ Enabled sound pack '{pack_name}' for Claude Code")
    else:
        click.echo(f"✗ Failed to enable pack '{pack_name}' for Claude Code", err=True)


@sfx.command("enable-opencode") 
@click.argument("pack_name")
def enable_opencode(pack_name: str) -> None:
    """Enable sound pack for Opencode."""
    manager = SoundPackManager()
    
    if manager.enable_for_opencode(pack_name):
        click.echo(f"✓ Enabled sound pack '{pack_name}' for Opencode")
        click.echo(f"  Plugin created in ~/.opencode/plugin/clod-sounds-{pack_name}.js")
    else:
        click.echo(f"✗ Failed to enable pack '{pack_name}' for Opencode", err=True)


@sfx.command("disable-claude")
@click.argument("pack_name")
def disable_claude(pack_name: str) -> None:
    """Disable sound pack for Claude Code."""
    manager = SoundPackManager()
    
    if manager.disable_for_claude_code(pack_name):
        click.echo(f"✓ Disabled sound pack '{pack_name}' for Claude Code")
    else:
        click.echo(f"✗ Failed to disable pack '{pack_name}' for Claude Code", err=True)


@sfx.command("disable-opencode")
@click.argument("pack_name") 
def disable_opencode(pack_name: str) -> None:
    """Disable sound pack for Opencode."""
    manager = SoundPackManager()
    
    if manager.disable_for_opencode(pack_name):
        click.echo(f"✓ Disabled sound pack '{pack_name}' for Opencode")
    else:
        click.echo(f"✗ Failed to disable pack '{pack_name}' for Opencode", err=True)


@sfx.command("uninstall")
@click.argument("pack_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def uninstall_pack(pack_name: str, yes: bool) -> None:
    """Uninstall a sound pack completely."""
    manager = SoundPackManager()
    
    # Check if pack exists
    if not manager.get_pack_schema(pack_name):
        click.echo(f"✗ Sound pack '{pack_name}' not found", err=True)
        return
    
    if not yes:
        click.confirm(f"Uninstall sound pack '{pack_name}'?", abort=True)
    
    if manager.uninstall_pack(pack_name):
        click.echo(f"✓ Uninstalled sound pack '{pack_name}'")
    else:
        click.echo(f"✗ Failed to uninstall pack '{pack_name}'", err=True)


@sfx.command("info")
@click.argument("pack_name")
def pack_info(pack_name: str) -> None:
    """Show detailed information about a sound pack."""
    manager = SoundPackManager()
    pack_schema = manager.get_pack_schema(pack_name)
    
    if not pack_schema:
        click.echo(f"✗ Sound pack '{pack_name}' not found", err=True)
        return
    
    click.echo(f"Sound Pack: {pack_schema.name}")
    click.echo(f"Version: {pack_schema.version}")
    if pack_schema.description:
        click.echo(f"Description: {pack_schema.description}")
    if pack_schema.author:
        click.echo(f"Author: {pack_schema.author}")
    if pack_schema.tags:
        click.echo(f"Tags: {', '.join(pack_schema.tags)}")
    
    click.echo(f"\nSound Events ({len(pack_schema.events)}):")
    for event_name, event_config in pack_schema.events.items():
        status = "✓" if event_config.enabled else "✗"
        volume_info = f" (volume: {event_config.volume})" if event_config.volume != 1.0 else ""
        click.echo(f"  {status} {event_name}: {event_config.sound_file}{volume_info}")
    
    # Show Claude Code mapping
    click.echo("\nClaude Code Event Mapping:")
    for opencode_event in pack_schema.events.keys():
        claude_event = manager.REVERSE_EVENT_MAPPING.get(opencode_event, "No mapping")
        click.echo(f"  {opencode_event} -> {claude_event}")


@sfx.command("create-example")
@click.argument("output_dir", type=click.Path(path_type=Path))
def create_example_pack(output_dir: Path) -> None:
    """Create an example sound pack template."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create example sounds.json
    example_schema = {
        "name": "Example Sound Pack",
        "version": "1.0.0", 
        "description": "An example sound pack demonstrating the schema",
        "author": "Your Name",
        "tags": ["example", "demo"],
        "events": {
            "tool.execute.before": {
                "sound_file": "start.wav",
                "enabled": True,
                "volume": 0.8
            },
            "tool.execute.after": {
                "sound_file": "complete.wav", 
                "enabled": True,
                "volume": 1.0
            },
            "session.idle": {
                "sound_file": "idle.wav",
                "enabled": False,
                "volume": 0.5
            }
        }
    }
    
    sounds_json = output_dir / "sounds.json"
    with sounds_json.open("w") as f:
        json.dump(example_schema, f, indent=2)
    
    # Create example sound files (just placeholder files)
    for event_config in example_schema["events"].values():
        sound_file = output_dir / event_config["sound_file"] 
        sound_file.touch()
    
    click.echo(f"✓ Created example sound pack in {output_dir}")
    click.echo("  - Edit sounds.json to configure events")
    click.echo("  - Replace .wav files with actual sound files")
    click.echo("  - Install with: clod sfx install /path/to/pack")


if __name__ == "__main__":
    main()
