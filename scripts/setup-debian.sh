#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y git curl unzip fontconfig libharfbuzz-bin
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv python install
uv sync --locked --extra dev
