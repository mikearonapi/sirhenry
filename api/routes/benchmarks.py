"""Benchmarking and Financial Order of Operations endpoints."""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.planning.action_plan import compute_action_plan, compute_benchmarks_from_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("/snapshot")
async def benchmark_snapshot(session: AsyncSession = Depends(get_session)):
    return await compute_benchmarks_from_db(session)


@router.get("/order-of-operations")
async def order_of_operations(session: AsyncSession = Depends(get_session)):
    return await compute_action_plan(session)
