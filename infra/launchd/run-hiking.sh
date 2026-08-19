#!/usr/bin/env bash
# Wrapper that launchd points at. Resolves the project root from this
# script's location so the plist doesn't need to hardcode user paths beyond
# pointing at this file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT/backend"

# shellcheck disable=SC1091
source .venv/bin/activate
exec python app.py
