"""Plaid Income endpoints: link token, sync trigger, connection listing."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import AsyncSessionLocal, get_session
from pipeline.db.schema import PayrollConnection, PayStubRecord
from pipeline.db.encryption import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/income", tags=["income"])


class IncomeConnectionIn(BaseModel):
    income_source_type: str = "payroll"


@router.post("/link-token")
async def get_income_link_token(
    body: IncomeConnectionIn,
    session: AsyncSession = Depends(get_session),
):
    """Create Plaid user + income Link token."""
    from pipeline.plaid.income_client import create_plaid_user, create_income_link_token

    # Check for existing connection with user credentials
    existing = await session.execute(
        select(PayrollConnection).order_by(PayrollConnection.created_at.desc()).limit(1)
    )
    conn = existing.scalar_one_or_none()

    user_token = ""
    user_id = ""

    if conn and (conn.plaid_user_token or conn.plaid_user_id):
        # Reuse existing credentials
        if conn.plaid_user_token:
            decrypted = decrypt_token(conn.plaid_user_token)
            if decrypted:  # empty string means no real token
                user_token = decrypted
        if conn.plaid_user_id:
            user_id = conn.plaid_user_id
    else:
        # Create new Plaid user
        try:
            user_data = create_plaid_user("sirhenry-default-user")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        user_token = user_data["user_token"]
        user_id = user_data["user_id"]

        if not user_token:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Employer connection requires the Plaid Income product. "
                    "Enable Income verification in your Plaid Dashboard, "
                    "or contact Plaid to activate it for your account."
                ),
            )

        conn = PayrollConnection(
            plaid_user_token=encrypt_token(user_token) if user_token else encrypt_token(""),
            plaid_user_id=user_id or None,
            income_source_type=body.income_source_type,
            status="pending",
        )
        session.add(conn)
        await session.flush()

    try:
        link_token = create_income_link_token(
            income_source_type=body.income_source_type,
            user_token=user_token,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create income link: {e}")
    return {"link_token": link_token, "connection_id": conn.id}


@router.post("/connected/{connection_id}")
async def income_connected(
    connection_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Called after user completes income Link flow. Triggers background sync."""
    result = await session.execute(
        select(PayrollConnection).where(PayrollConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, "Connection not found")

    conn.status = "syncing"
    await session.flush()

    background_tasks.add_task(_sync_income_background, connection_id)
    return {"status": "syncing", "connection_id": connection_id}


async def _sync_income_background(connection_id: int) -> None:
    """Background: fetch payroll data and cascade to all tables."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(PayrollConnection).where(PayrollConnection.id == connection_id)
            )
            conn = result.scalar_one_or_none()
            if not conn:
                return

            try:
                from pipeline.plaid.income_client import get_payroll_income
                from pipeline.plaid.income_sync import sync_payroll_to_household

                user_token = decrypt_token(conn.plaid_user_token) if conn.plaid_user_token else ""
                if not user_token:  # empty encrypted string
                    user_token = ""
                user_id = conn.plaid_user_id or ""
                payroll_data = get_payroll_income(user_token=user_token, user_id=user_id)
                counts = await sync_payroll_to_household(session, conn, payroll_data)
                logger.info("Income sync complete for connection %d: %s", connection_id, counts)
            except Exception as e:
                logger.error("Income sync failed for connection %d: %s", connection_id, e)
                conn.status = "error"


@router.get("/connections")
async def list_connections(session: AsyncSession = Depends(get_session)):
    """List all payroll/income connections."""
    result = await session.execute(
        select(PayrollConnection).order_by(PayrollConnection.created_at.desc())
    )
    connections = list(result.scalars().all())
    return [
        {
            "id": c.id,
            "employer_name": c.employer_name,
            "status": c.status,
            "income_source_type": c.income_source_type,
            "last_synced_at": str(c.last_synced_at) if c.last_synced_at else None,
        }
        for c in connections
    ]


@router.get("/cascade-summary/{connection_id}")
async def cascade_summary(
    connection_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Show what data was imported from this income connection."""
    result = await session.execute(
        select(PayrollConnection).where(PayrollConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, "Connection not found")

    # Count pay stubs
    stubs_result = await session.execute(
        select(PayStubRecord).where(PayStubRecord.connection_id == connection_id)
    )
    stubs = list(stubs_result.scalars().all())

    # Derive summary from stored data
    latest_stub = sorted(stubs, key=lambda s: str(s.pay_date), reverse=True)[0] if stubs else None
    annual_income = None
    benefits_detected: list[str] = []

    if latest_stub:
        from pipeline.plaid.income_sync import _estimate_annual_income
        annual_income = _estimate_annual_income({
            "gross_pay_ytd": latest_stub.gross_pay_ytd,
            "gross_pay": latest_stub.gross_pay,
            "pay_date": str(latest_stub.pay_date),
            "pay_frequency": latest_stub.pay_frequency,
        })
        # Parse deductions for benefit names
        try:
            deds = __import__("json").loads(latest_stub.deductions_json or "[]")
            benefits_detected = [d.get("description", "") for d in deds if d.get("description")]
        except Exception:
            pass

    return {
        "connection_id": connection_id,
        "status": conn.status,
        "employer": conn.employer_name,
        "annual_income": annual_income,
        "pay_stubs_imported": len(stubs),
        "benefits_detected": benefits_detected[:10],
        "last_synced_at": str(conn.last_synced_at) if conn.last_synced_at else None,
    }
