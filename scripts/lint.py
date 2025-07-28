#!/usr/bin/env python3
"""Lint script for clod."""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a command and return success status."""
    print(f"Running {description}...")
    result = subprocess.run(cmd, shell=True, cwd=Path(__file__).parent.parent)
    if result.returncode != 0:
        print(f"❌ {description} failed")
        return False
    print(f"✅ {description} passed")
    return True


def main() -> None:
    """Run all linting checks."""
    checks = [
        ("ruff check .", "ruff linting"),
        ("ruff format --check .", "ruff formatting"),
        ("mypy .", "mypy type checking"),
    ]

    all_passed = True
    for cmd, desc in checks:
        if not run_command(cmd, desc):
            all_passed = False

    if not all_passed:
        sys.exit(1)

    print("🎉 All checks passed!")


if __name__ == "__main__":
    main()
