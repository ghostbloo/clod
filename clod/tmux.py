"""Tmux control utilities for Claude workspace management."""

import subprocess
import time
from datetime import datetime
from pathlib import Path


class TmuxController:
    """Control tmux sessions for Claude workspace management."""

    def __init__(self, session_name: str = "claude-workspace") -> None:
        self.session_name = session_name
        self.target_pane = f"{session_name}:cc.1"

    def _run_tmux(self, *args: str) -> subprocess.CompletedProcess:
        """Run a tmux command and return the result."""
        return subprocess.run(["tmux", *list(args)], capture_output=True, text=True)

    def has_session(self) -> bool:
        """Check if the Claude session exists."""
        result = self._run_tmux("has-session", "-t", self.session_name)
        return result.returncode == 0

    def setup(self, working_dir: Path | None = None) -> bool:
        """Set up the Claude tmux workspace."""
        if self.has_session():
            print(f"Session '{self.session_name}' already exists")
            return False

        cwd = str(working_dir or Path.cwd())

        # Create session with first window named "cc" and split vertically
        # (85% top user, 15% bottom Claude)
        self._run_tmux(
            "new-session", "-d", "-s", self.session_name, "-c", cwd, "-n", "cc"
        )
        self._run_tmux(
            "split-window",
            "-v",
            "-p",
            "15",
            "-t",
            f"{self.session_name}:cc",
            "-c",
            cwd,
        )

        # Create second window named "pm2" running pm2 monitor
        self._run_tmux(
            "new-window",
            "-t",
            self.session_name,
            "-c",
            cwd,
            "-n",
            "pm2",
            "pm2 monit",
        )

        # Switch back to the cc window
        self._run_tmux("select-window", "-t", f"{self.session_name}:cc")

        # Send initial messages to Claude pane in cc window
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.send_keys(f"echo 'Claude control pane ready ({timestamp})'")
        self.send_keys(f"echo 'Working directory: {cwd}'")

        msg = (
            f"Claude workspace created! "
            f"Use 'tmux attach -t {self.session_name}' to view"
        )
        print(msg)
        print("Windows: 'cc' (main workspace), 'pm2' (pm2 monitor)")
        print("Or press prefix+c to switch to it from existing sessions")
        return True

    def send_keys(self, command: str) -> bool:
        """Send a command to the Claude pane."""
        if not self.has_session():
            print("Claude session doesn't exist. Run setup first.")
            return False

        print(f"Sending command to Claude pane: {command}")
        result = self._run_tmux("send-keys", "-t", self.target_pane, command, "Enter")
        return result.returncode == 0

    def read_output(self, lines: int = 20) -> str:
        """Read output from the Claude pane."""
        if not self.has_session():
            print("Claude session doesn't exist. Run setup first.")
            return ""

        result = self._run_tmux("capture-pane", "-t", self.target_pane, "-p")
        if result.returncode != 0:
            return ""

        output_lines = result.stdout.strip().split("\n")
        return "\n".join(output_lines[-lines:]) if output_lines else ""

    def status(self) -> dict:
        """Get status information about the Claude session."""
        if not self.has_session():
            return {"exists": False}

        panes_result = self._run_tmux("list-panes", "-t", self.session_name)
        windows_result = self._run_tmux("list-windows", "-t", self.session_name)

        return {
            "exists": True,
            "session_name": self.session_name,
            "panes": (
                len(panes_result.stdout.strip().split("\n"))
                if panes_result.stdout.strip()
                else 0
            ),
            "windows": (
                len(windows_result.stdout.strip().split("\n"))
                if windows_result.stdout.strip()
                else 0
            ),
        }

    def kill_session(self) -> bool:
        """Kill the Claude session."""
        if not self.has_session():
            print("No Claude session to kill")
            return False

        result = self._run_tmux("kill-session", "-t", self.session_name)
        if result.returncode == 0:
            print("Claude session killed")
            return True
        return False

    # REPL-specific methods
    def start_repl(self, command: str, working_dir: Path | None = None) -> bool:
        """Start a REPL session with the specified command."""
        if self.has_session():
            print(f"Session '{self.session_name}' already exists")
            return False

        cwd = str(working_dir or Path.cwd())

        # Create session and run the command
        result = self._run_tmux(
            "new-session", "-d", "-s", self.session_name, "-c", cwd, command
        )
        if result.returncode == 0:
            print(f"REPL session started with: {command}")
            return True
        return False

    def send_input(self, text: str) -> bool:
        """Send text input without pressing Enter."""
        if not self.has_session():
            print(f"Session '{self.session_name}' doesn't exist")
            return False

        result = self._run_tmux("send-keys", "-t", self.session_name, text)
        return result.returncode == 0

    def send_raw_keys(self, *keys: str) -> bool:
        """Send raw key combinations."""
        if not self.has_session():
            print(f"Session '{self.session_name}' doesn't exist")
            return False

        result = self._run_tmux("send-keys", "-t", self.session_name, *keys)
        return result.returncode == 0

    def submit(self, mode: str = "standard") -> bool:
        """Submit current input with different submission modes."""
        if not self.has_session():
            print(f"Session '{self.session_name}' doesn't exist")
            return False

        if mode == "vim":
            # Escape + Enter for vim-style interfaces (sent separately with delay)
            escape_result = self._run_tmux(
                "send-keys", "-t", self.session_name, "Escape"
            )
            if escape_result.returncode != 0:
                return False
            time.sleep(0.1)  # Small delay for vim interface to process Escape
            result = self._run_tmux("send-keys", "-t", self.session_name, "Enter")
        elif mode == "standard":
            # Just Enter for most REPLs
            result = self._run_tmux("send-keys", "-t", self.session_name, "Enter")
        else:
            print(f"Unknown submission mode: {mode}")
            return False

        return result.returncode == 0

    def read_output_with_history(self, lines: int = 20, history_lines: int = 0) -> str:
        """Read output with optional scroll history."""
        if not self.has_session():
            print(f"Session '{self.session_name}' doesn't exist")
            return ""

        if history_lines > 0:
            result = self._run_tmux(
                "capture-pane",
                "-t",
                self.session_name,
                "-S",
                f"-{history_lines}",
                "-p",
            )
        else:
            result = self._run_tmux("capture-pane", "-t", self.session_name, "-p")

        if result.returncode != 0:
            return ""

        output_lines = result.stdout.strip().split("\n")
        if lines > 0 and output_lines:
            return "\n".join(output_lines[-lines:])
        return str(result.stdout.strip())
