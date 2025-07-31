#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# ///

import json
import subprocess
import sys


def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        if input_data.get('tool_name', '') in ['Write', 'Edit', 'MultiEdit']:
            # Run lint script
            try:
                result = subprocess.run(
                    ['uv', 'run', 'scripts/lint.py'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    print(f"Linting failed with exit code {result.returncode}:", file=sys.stderr)
                    if result.stdout:
                        print(result.stdout, file=sys.stderr)
                    if result.stderr:
                        print(result.stderr, file=sys.stderr)
            except subprocess.TimeoutExpired:
                print("Linting timed out after 30 seconds", file=sys.stderr)
            except Exception as e:
                print(f"Error running lint: {e}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError:
        sys.exit(1)

if __name__ == '__main__':
    main()
