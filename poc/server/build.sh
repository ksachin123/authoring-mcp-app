#!/usr/bin/env bash
set -euo pipefail

# Build the widget bundle first so the Python server can serve it as static files.
cd "$(dirname "$0")/../../widget"
npm install
npm run build

# Install the Python server package.
cd "$(dirname "$0")"
pip install -e ".[dev]"
