#!/bin/zsh
set -euo pipefail

tmux new-session -d -s clod-dev -c "$PWD" 'source ~/.zshrc && source .venv/bin/activate && exec zsh'
tmux attach-session -t clod-dev
