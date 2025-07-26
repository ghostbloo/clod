# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**clod** is a Python-based CLI providing various utilities, toys, and hacks for enhancing the Claude Code + Claude Desktop experience.

## Commands

### Setup
- `uv venv` + `uv sync` + `source .venv/bin/activate`
- Run lints with `ruff` and `mypy` as you go.
- Run `clod` for a list of commands.

## Project Structure
- `clod/` - Python sources
- `resources/sounds/` - Audio files for Claude Code events

## Development Guidelines

### Key Technologies
- **uv**: Python package manager
- **click**: CLI integration
- **Claude Code**
  - [Hooks](https://docs.anthropic.com/en/docs/claude-code/hooks)
  - [Guide](https://docs.anthropic.com/en/docs/claude-code/hooks-guide)
- **cchooks**: Package for managing Claude Code hooks
  - [README.md](https://github.com/GowayLee/cchooks/blob/main/README.md)
  - [docs](https://github.com/GowayLee/cchooks/tree/main/docs)
