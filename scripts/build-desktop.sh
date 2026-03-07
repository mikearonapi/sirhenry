#!/usr/bin/env bash
# Build SirHENRY desktop app for the current platform.
# Prerequisites: Rust toolchain, Python 3.12, Node.js 20+
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Ensure Rust is on PATH
if [ -f "$HOME/.cargo/env" ]; then
    . "$HOME/.cargo/env"
fi

echo "=== Step 1: Build Python sidecar ==="
bash "$ROOT/sidecar/build_sidecar.sh"

echo ""
echo "=== Step 2: Build Tauri app (includes frontend static export) ==="
cd "$ROOT/src-tauri"
cargo tauri build

echo ""
echo "=== Done ==="
echo "Output:"
ls -la "$ROOT/src-tauri/target/release/bundle/" 2>/dev/null || echo "(check src-tauri/target/release/bundle/)"
