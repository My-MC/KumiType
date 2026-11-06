#!/usr/bin/env bash
set -euo pipefail
# HarfBuzz CLI availability depends on the enabled RHEL repositories.
sudo dnf install -y git curl unzip fontconfig
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv python install
uv sync --locked --extra dev
