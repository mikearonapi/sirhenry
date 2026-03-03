"""
SirHENRY Local Stack Launcher
=============================
Starts both the FastAPI API server and the Next.js frontend without Docker.

Usage:
    python scripts/run_local.py              # default ports (API 8000, Frontend 3000)
    python scripts/run_local.py --api-port 8001 --frontend-port 3001
    python scripts/run_local.py --production  # uses 'next start' instead of 'next dev'

Prerequisites:
    python scripts/setup_local.py            # one-time setup
"""
import argparse
import os
import platform
import shutil
import signal
import socket
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
MIN_PYTHON = (3, 12)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _print_banner(msg: str) -> None:
    width = max(len(msg) + 4, 60)
    print()
    print("=" * width)
    print(f"  {msg}")
    print("=" * width)


def _print_status(label: str, value: str) -> None:
    print(f"  {label:<24s} {value}")


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _find_available_port(start: int, end: int = None) -> int:
    """Find an available port starting from *start*."""
    if end is None:
        end = start + 100
    for port in range(start, end):
        if _port_available(port):
            return port
    raise RuntimeError(f"No available port found in range {start}-{end}")


def _check_python() -> None:
    v = sys.version_info
    if (v.major, v.minor) < MIN_PYTHON:
        print(f"[ERROR] Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, "
              f"found {v.major}.{v.minor}.{v.micro}")
        sys.exit(1)
    _print_status("Python", f"{v.major}.{v.minor}.{v.micro}")


def _check_node() -> str:
    """Verify Node.js is available and return its version string."""
    node = shutil.which("node")
    if not node:
        print("[ERROR] Node.js not found on PATH. Install from https://nodejs.org/")
        sys.exit(1)
    try:
        out = subprocess.check_output([node, "--version"], text=True).strip()
    except subprocess.CalledProcessError:
        print("[ERROR] Could not determine Node.js version.")
        sys.exit(1)
    _print_status("Node.js", out)
    return out


def _check_npm() -> str:
    npm = shutil.which("npm")
    if not npm:
        print("[ERROR] npm not found on PATH.")
        sys.exit(1)
    try:
        out = subprocess.check_output([npm, "--version"], text=True).strip()
    except subprocess.CalledProcessError:
        out = "unknown"
    _print_status("npm", out)
    return npm


def _ensure_env_file() -> None:
    if ENV_FILE.exists():
        _print_status(".env", "found")
        return
    if ENV_EXAMPLE.exists():
        shutil.copy2(ENV_EXAMPLE, ENV_FILE)
        _print_status(".env", "copied from .env.example (edit values before use)")
    else:
        print("[WARN] No .env or .env.example found. Some features may not work.")


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _print_status("Data dir", str(DATA_DIR))


def _ensure_node_modules(npm: str) -> None:
    nm = FRONTEND_DIR / "node_modules"
    if nm.is_dir():
        _print_status("node_modules", "found")
        return
    print()
    print("  frontend/node_modules not found.")
    answer = input("  Run 'npm install' now? [Y/n] ").strip().lower()
    if answer in ("", "y", "yes"):
        print("  Installing frontend dependencies...")
        subprocess.check_call([npm, "install"], cwd=str(FRONTEND_DIR))
        _print_status("node_modules", "installed")
    else:
        print("[WARN] Skipping npm install. Frontend may not start.")


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------
_children: list[subprocess.Popen] = []


def _shutdown(signum=None, frame=None) -> None:
    """Gracefully terminate child processes."""
    print("\n\n  Shutting down...")
    for proc in reversed(_children):
        if proc.poll() is None:
            try:
                if platform.system() == "Windows":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.terminate()
            except OSError:
                pass
    for proc in _children:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("  All processes stopped.")


def _register_signals() -> None:
    if platform.system() == "Windows":
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGBREAK, _shutdown)
    else:
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)


def _start_api(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    db_url = f"sqlite+aiosqlite:///{DATA_DIR}/financials.db"
    env["DATABASE_URL"] = db_url
    env["API_HOST"] = "127.0.0.1"
    env["API_PORT"] = str(port)

    cmd = [
        sys.executable, "-m", "uvicorn",
        "api.main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--reload",
    ]
    _print_status("API command", " ".join(cmd))

    creation_flags = 0
    if platform.system() == "Windows":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        creationflags=creation_flags,
    )
    _children.append(proc)
    return proc


def _start_frontend(port: int, api_port: int, production: bool = False) -> subprocess.Popen:
    npm = shutil.which("npm")
    env = os.environ.copy()
    env["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{api_port}"
    env["PORT"] = str(port)

    if production:
        # Build first, then start
        print("  Building frontend for production...")
        subprocess.check_call(
            [npm, "run", "build"],
            cwd=str(FRONTEND_DIR),
            env=env,
        )
        cmd = [npm, "run", "start"]
    else:
        cmd = [npm, "run", "dev"]

    _print_status("Frontend command", " ".join(cmd))

    creation_flags = 0
    if platform.system() == "Windows":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        cmd,
        cwd=str(FRONTEND_DIR),
        env=env,
        creationflags=creation_flags,
    )
    _children.append(proc)
    return proc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start the SirHENRY stack locally (API + Frontend)",
    )
    parser.add_argument(
        "--api-port", type=int, default=8000,
        help="Port for the FastAPI server (default: 8000)",
    )
    parser.add_argument(
        "--frontend-port", type=int, default=3000,
        help="Port for the Next.js frontend (default: 3000)",
    )
    parser.add_argument(
        "--production", action="store_true",
        help="Run frontend in production mode (next build + next start)",
    )
    args = parser.parse_args()

    _print_banner("SirHENRY Local Launcher")

    # Pre-flight checks
    print("\n  Checking prerequisites...")
    _check_python()
    _check_node()
    npm = _check_npm()
    _ensure_env_file()
    _ensure_data_dir()
    _ensure_node_modules(npm)

    # Resolve ports
    api_port = args.api_port
    if not _port_available(api_port):
        api_port = _find_available_port(api_port + 1)
        print(f"  [INFO] Port {args.api_port} in use, using {api_port} for API")

    frontend_port = args.frontend_port
    if not _port_available(frontend_port):
        frontend_port = _find_available_port(frontend_port + 1)
        print(f"  [INFO] Port {args.frontend_port} in use, using {frontend_port} for Frontend")

    # Register signal handlers
    _register_signals()

    # Start services
    _print_banner("Starting API server")
    api_proc = _start_api(api_port)

    _print_banner("Starting Frontend")
    fe_proc = _start_frontend(frontend_port, api_port, production=args.production)

    _print_banner("SirHENRY is running")
    _print_status("API", f"http://127.0.0.1:{api_port}")
    _print_status("API docs", f"http://127.0.0.1:{api_port}/docs")
    _print_status("Frontend", f"http://127.0.0.1:{frontend_port}")
    _print_status("Database", str(DATA_DIR / "financials.db"))
    print()
    print("  Press Ctrl+C to stop all services.")
    print()

    # Wait for either process to exit
    try:
        while True:
            if api_proc.poll() is not None:
                print(f"\n  [WARN] API server exited with code {api_proc.returncode}")
                break
            if fe_proc.poll() is not None:
                print(f"\n  [WARN] Frontend exited with code {fe_proc.returncode}")
                break
            try:
                api_proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown()


if __name__ == "__main__":
    main()
