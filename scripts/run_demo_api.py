"""Launch the API server pointed at the demo database.

Usage (from project root):
    python scripts/run_demo_api.py

The .env file has DATABASE_URL with override=True via load_dotenv,
so we must import pipeline.utils first (which triggers load_dotenv),
then override the module-level DATABASE_URL constant before api.database
is imported and creates the engine.
"""
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'api' package is importable
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_home = str(Path.home())
DEMO_URL = f"sqlite+aiosqlite:///{_home}/.sirhenry/data/demo.db"

# Step 1: Import pipeline.utils — this triggers load_dotenv(override=True)
# which reads DATABASE_URL from .env and sets it as the module constant
import pipeline.utils

# Step 2: Override the module-level constant with our demo URL
pipeline.utils.DATABASE_URL = DEMO_URL
os.environ["DATABASE_URL"] = DEMO_URL

print(f"[demo] DATABASE_URL override: {DEMO_URL}")

# Step 3: Now import and run uvicorn — when api.database imports
# DATABASE_URL from pipeline.utils, it will get our demo value
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8001,
        reload=False,
    )
