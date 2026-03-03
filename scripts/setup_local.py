"""
SirHENRY Local Setup
====================
One-time setup for running SirHENRY locally without Docker.

What it does:
    1. Creates ~/.sirhenry/data/ directory
    2. Copies .env.example to .env if .env doesn't exist
    3. Installs Python dependencies (pip install -r requirements.txt)
    4. Installs frontend dependencies (cd frontend && npm install)
    5. Prints next steps

Usage:
    python scripts/setup_local.py
    python scripts/setup_local.py --skip-pip    # skip Python deps
    python scripts/setup_local.py --skip-npm    # skip Node deps
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
DATA_DIR = Path.home() / ".sirhenry" / "data"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
MIN_PYTHON = (3, 12)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _header(msg: str) -> None:
    print()
    print(f"  [{msg}]")
    print("  " + "-" * (len(msg) + 2))


def _ok(msg: str) -> None:
    print(f"    OK  {msg}")


def _skip(msg: str) -> None:
    print(f"    --  {msg}")


def _fail(msg: str) -> None:
    print(f"    !!  {msg}")


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
def step_check_python() -> None:
    _header("Checking Python version")
    v = sys.version_info
    if (v.major, v.minor) < MIN_PYTHON:
        _fail(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, "
              f"found {v.major}.{v.minor}.{v.micro}")
        sys.exit(1)
    _ok(f"Python {v.major}.{v.minor}.{v.micro}")


def step_check_node() -> None:
    _header("Checking Node.js")
    node = shutil.which("node")
    if not node:
        _fail("Node.js not found. Install from https://nodejs.org/")
        sys.exit(1)
    try:
        ver = subprocess.check_output([node, "--version"], text=True).strip()
    except subprocess.CalledProcessError:
        ver = "unknown"
    _ok(f"Node.js {ver}")

    npm = shutil.which("npm")
    if not npm:
        _fail("npm not found on PATH.")
        sys.exit(1)
    try:
        ver = subprocess.check_output([npm, "--version"], text=True).strip()
    except subprocess.CalledProcessError:
        ver = "unknown"
    _ok(f"npm {ver}")


def step_create_data_dir() -> None:
    _header("Creating data directory")
    if DATA_DIR.exists():
        _ok(f"{DATA_DIR} (already exists)")
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _ok(f"{DATA_DIR} (created)")


def step_copy_env() -> None:
    _header("Setting up .env file")
    if ENV_FILE.exists():
        _ok(".env already exists (not overwriting)")
        return
    if ENV_EXAMPLE.exists():
        shutil.copy2(ENV_EXAMPLE, ENV_FILE)
        _ok(".env copied from .env.example")
        print("    >>> Edit .env to add your API keys before running the app.")
    else:
        _skip("No .env.example found; skipping")


def step_install_pip(skip: bool = False) -> None:
    _header("Installing Python dependencies")
    if skip:
        _skip("Skipped (--skip-pip)")
        return
    if not REQUIREMENTS.exists():
        _fail("requirements.txt not found")
        return
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
            cwd=str(PROJECT_ROOT),
        )
        _ok("Python dependencies installed")
    except subprocess.CalledProcessError as exc:
        _fail(f"pip install failed (exit code {exc.returncode})")
        print("    Try running manually: pip install -r requirements.txt")


def step_install_npm(skip: bool = False) -> None:
    _header("Installing frontend dependencies")
    if skip:
        _skip("Skipped (--skip-npm)")
        return
    npm = shutil.which("npm")
    if not npm:
        _fail("npm not found")
        return
    try:
        subprocess.check_call([npm, "install"], cwd=str(FRONTEND_DIR))
        _ok("Frontend dependencies installed")
    except subprocess.CalledProcessError as exc:
        _fail(f"npm install failed (exit code {exc.returncode})")
        print("    Try running manually: cd frontend && npm install")


def step_print_next_steps() -> None:
    print()
    print("=" * 60)
    print("  Setup complete! Next steps:")
    print("=" * 60)
    print()
    print("  1. Edit .env with your API keys:")
    print(f"     {ENV_FILE}")
    print()
    print("  2. Start the full stack:")
    print("     python scripts/run_local.py")
    print()
    print("  3. Open the app:")
    print("     http://localhost:3000")
    print()
    print("  4. API docs:")
    print("     http://localhost:8000/docs")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time setup for running SirHENRY locally",
    )
    parser.add_argument("--skip-pip", action="store_true", help="Skip pip install")
    parser.add_argument("--skip-npm", action="store_true", help="Skip npm install")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  SirHENRY Local Setup")
    print("=" * 60)

    step_check_python()
    step_check_node()
    step_create_data_dir()
    step_copy_env()
    step_install_pip(skip=args.skip_pip)
    step_install_npm(skip=args.skip_npm)
    step_print_next_steps()


if __name__ == "__main__":
    main()
