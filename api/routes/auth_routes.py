"""Auth-related endpoints — mode selection, API key delivery, and session info."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from api.models.schemas import InjectApiKeyIn
from api.database import get_active_mode, switch_to_mode

router = APIRouter(prefix="/auth", tags=["auth"])


class SelectModeBody(BaseModel):
    mode: str  # "local" | "demo"


@router.post("/select-mode")
async def select_mode(body: SelectModeBody):
    """
    Switch the active database mode.
    - "local": user's real financial data
    - "demo": synthetic demo data (auto-initialized on first use)
    """
    if body.mode not in ("local", "demo"):
        raise HTTPException(status_code=400, detail="Mode must be 'local' or 'demo'")
    result = await switch_to_mode(body.mode)
    return {"status": "ok", "mode": result}


@router.get("/mode")
async def get_mode():
    """Return the current database mode."""
    return {"mode": get_active_mode()}


@router.post("/inject-api-key")
async def inject_api_key(
    body: InjectApiKeyIn,
    user: dict | None = Depends(get_current_user),
):
    """
    Receive the Anthropic API key from the frontend
    (fetched via Supabase Edge Function after authentication).
    Stores it in the process environment for the current session.
    """
    key = body.key
    if not key.startswith("sk-ant-"):
        raise HTTPException(status_code=400, detail="Invalid API key format")
    os.environ["ANTHROPIC_API_KEY"] = key
    return {"status": "ok"}


@router.get("/me")
async def get_me(user: dict | None = Depends(get_current_user)):
    """Return the current user's JWT payload (for frontend session checks)."""
    if user is None:
        return {"authenticated": False, "demo_mode": get_active_mode() == "demo"}
    return {
        "authenticated": True,
        "user_id": user.get("sub"),
        "email": user.get("email"),
    }
