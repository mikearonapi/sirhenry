#!/usr/bin/env bash
# Build the PyInstaller sidecar for the current platform.
# Output: src-tauri/binaries/sirhenry-api/ (one-dir bundle)
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
rm -rf src-tauri/binaries/sirhenry-api

# Build sidecar
echo "Running PyInstaller..."
.venv/bin/pyinstaller sidecar/sirhenry-api.spec \
    --distpath src-tauri/binaries \
    --clean \
    --noconfirm

echo "=== Sidecar built at src-tauri/binaries/sirhenry-api/ ==="
ls -lh src-tauri/binaries/sirhenry-api/
