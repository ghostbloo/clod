#!/usr/bin/env python3
"""Format script for clod."""

import subprocess
from pathlib import Path


def main() -> None:
    """Format code with ruff."""
    print("Formatting code...")
    subprocess.run(
        "ruff check --fix . && ruff format .",
        shell=True,
        cwd=Path(__file__).parent.parent,
    )
    print("✅ Code formatted")


if __name__ == "__main__":
    main()
