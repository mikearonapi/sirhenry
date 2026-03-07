#!/usr/bin/env bash
# Build the PyInstaller sidecar for the current platform.
# Output: single executable at src-tauri/binaries/sirhenry-api-{target_triple}
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Building SirHENRY API sidecar ==="

# Ensure venv exists
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Install deps + PyInstaller
echo "Installing dependencies..."
.venv/bin/pip install -q -r requirements.txt pyinstaller

# Clean previous build
rm -rf src-tauri/binaries/sirhenry-api-*

# Build sidecar (one-file mode — outputs single executable)
echo "Running PyInstaller..."
mkdir -p src-tauri/binaries
.venv/bin/pyinstaller sidecar/sirhenry-api.spec \
    --distpath src-tauri/binaries \
    --clean \
    --noconfirm

echo "=== Sidecar built ==="
ls -lh src-tauri/binaries/sirhenry-api-*
