"""
SirHENRY API sidecar entry point for desktop app.
Finds a free port, writes it to a port file, and starts the FastAPI server.
"""
import os
import signal
import socket
import sys


def get_free_port() -> int:
    """Bind to port 0 to let the OS assign a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    # Set working directory to ~/.sirhenry/ so dotenv finds .env there
    home = os.path.expanduser("~")
    sirhenry_dir = os.path.join(home, ".sirhenry")
    data_dir = os.path.join(sirhenry_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    os.chdir(sirhenry_dir)

    # Load .env from ~/.sirhenry/.env
    from dotenv import load_dotenv
    env_path = os.path.join(sirhenry_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)

    # Override settings that must differ in desktop context.
    # DATABASE_URL: .env may have a relative dev path; force absolute path to ~/.sirhenry/data/
    db_path = os.path.join(data_dir, "financials.db")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    # Remove dev-only vars that conflict with desktop sidecar
    os.environ.pop("API_PORT", None)
    os.environ.pop("NEXT_PUBLIC_API_URL", None)

    # Find free port (or use explicit override)
    port = int(os.environ.get("SIRHENRY_PORT", "0"))
    if port == 0:
        port = get_free_port()

    # Write port file for Tauri to discover
    port_file = os.path.join(data_dir, ".api-port")
    with open(port_file, "w") as f:
        f.write(str(port))

    # Print to stdout for Tauri to read as backup
    print(f"SIRHENRY_PORT={port}", flush=True)

    # Cleanup on shutdown
    def cleanup(signum, frame):
        try:
            os.remove(port_file)
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    # Start uvicorn
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        workers=1,
    )


if __name__ == "__main__":
    main()
