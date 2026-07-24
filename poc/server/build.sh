#!/usr/bin/env bash
set -euo pipefail

SERVER_DIR="$(cd "$(dirname "$0")" && pwd)"

# Build the widget bundle first so the Python server can serve it as static files.
cd "$SERVER_DIR/../widget"
npm install
npm run build

# Install the Python server package.
cd "$SERVER_DIR"
pip install -e ".[dev]"
