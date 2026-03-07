"""
Shared utilities for the pipeline — eliminates duplication across importers.
"""
import hashlib
import logging
import os
import time

import pandas as pd

logger = logging.getLogger(__name__)
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

load_dotenv()

def _default_database_url() -> str:
    """Resolve the default database path, preferring a user-home directory when available."""
    env_val = os.getenv("DATABASE_URL")
    if env_val:
        return env_val
    # User-home-aware default: ~/.sirhenry/data/financials.db
    home = os.path.expanduser("~")
    data_dir = os.path.join(home, ".sirhenry", "data")
    os.makedirs(data_dir, exist_ok=True)
    return f"sqlite+aiosqlite:///{data_dir}/financials.db"

DATABASE_URL = _default_database_url()


def file_hash(filepath: str) -> str:
    """SHA-256 hash of a file's contents. Used for document dedup."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def to_float(val) -> float:
    """Safely convert a string/number value to float, stripping $ and commas."""
    if pd.isna(val) or val is None or val == "":
        return 0.0
    s = str(val).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        logger.warning("to_float: could not convert %r — returning 0.0", val)
        return 0.0


CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")


def strip_json_fences(raw: str) -> str:
    """Strip markdown code fences (```json ... ```) that LLMs sometimes wrap around JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


_claude_client = None


def get_claude_client():
    global _claude_client
    if _claude_client is None:
        import anthropic
        _claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _claude_client


def call_claude_with_retry(client, max_retries=3, **kwargs):
    """Call Claude API with exponential backoff retry on rate limits/transient errors."""
    for attempt in range(max_retries):
        try:
            return client.messages.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if attempt == max_retries - 1 or not any(
                w in err_str for w in ("rate", "overloaded", "timeout", "529")
            ):
                raise
            wait = 2 ** attempt
            time.sleep(wait)


_async_claude_client = None


def get_async_claude_client():
    """Singleton async Anthropic client for importers that need async API calls."""
    global _async_claude_client
    if _async_claude_client is None:
        import anthropic
        _async_claude_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _async_claude_client


async def call_claude_async_with_retry(client, max_retries=3, **kwargs):
    """Async Claude API call with exponential backoff retry on rate limits/transient errors."""
    import asyncio
    for attempt in range(max_retries):
        try:
            return await client.messages.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if attempt == max_retries - 1 or not any(
                w in err_str for w in ("rate", "overloaded", "timeout", "529")
            ):
                raise
            wait = 2 ** attempt
            await asyncio.sleep(wait)


def create_engine_and_session() -> tuple[AsyncEngine, async_sessionmaker]:
    """Create the shared async engine + session factory for CLI importer scripts."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory
