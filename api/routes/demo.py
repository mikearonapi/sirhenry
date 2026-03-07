"""Demo mode — seed, reset, and status endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.demo.seeder import get_demo_status, reset_demo_data, seed_demo_data

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/seed")
async def seed_demo(session: AsyncSession = Depends(get_session)):
    """Populate the database with synthetic demo data.
    Returns counts of created records. Fails if DB already has data."""
    try:
        result = await seed_demo_data(session)
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/reset")
async def reset_demo(session: AsyncSession = Depends(get_session)):
    """Clear all tables and remove demo mode flag. Only works when in demo mode."""
    status = await get_demo_status(session)
    if not status["active"]:
        raise HTTPException(status_code=409, detail="Not in demo mode — reset refused to protect real data.")
    await reset_demo_data(session)
    return {"status": "ok"}


@router.get("/status")
async def demo_status(session: AsyncSession = Depends(get_session)):
    """Check whether the app is currently in demo mode."""
    return await get_demo_status(session)
