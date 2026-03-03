import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import ChatRequestIn, ChatResponseOut
from pipeline.ai.chat import run_chat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponseOut)
async def send_message(
    body: ChatRequestIn,
    session: AsyncSession = Depends(get_session),
):
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    result = await run_chat(session, messages)

    await session.flush()

    return ChatResponseOut(
        response=result["response"],
        actions=result.get("actions", []),
        tool_calls_made=result.get("tool_calls_made", 0),
    )
