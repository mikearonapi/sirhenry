import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import get_session
from api.models.schemas import (
    ChatConversationDetailOut,
    ChatConversationOut,
    ChatRequestIn,
    ChatResponseOut,
)
from pipeline.ai.chat import run_chat, run_chat_stream
from pipeline.db.schema import ChatConversation, ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponseOut)
async def send_message(
    body: ChatRequestIn,
    session: AsyncSession = Depends(get_session),
):
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    result = await run_chat(
        session,
        messages,
        conversation_id=body.conversation_id,
        page_context=body.page_context,
    )

    await session.flush()

    return ChatResponseOut(
        response=result.get("response"),
        requires_consent=result.get("requires_consent", False),
        actions=result.get("actions", []),
        tool_calls_made=result.get("tool_calls_made", 0),
        conversation_id=result.get("conversation_id"),
    )


@router.post("/stream")
async def stream_message(
    body: ChatRequestIn,
    session: AsyncSession = Depends(get_session),
):
    """
    Streaming chat endpoint. Returns Server-Sent Events (text/event-stream).

    Events:
        data: {"type": "text_delta", "text": "..."}
        data: {"type": "tool_start", "tool": "...", "label": "..."}
        data: {"type": "tool_done",  "tool": "...", "label": "...", "preview": "..."}
        data: {"type": "done", "conversation_id": 123, "actions": [...]}
        data: {"type": "requires_consent"}
        data: {"type": "error", "message": "..."}
        data: [DONE]
    """
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def event_generator():
        try:
            async for event in run_chat_stream(
                session,
                messages,
                conversation_id=body.conversation_id,
                page_context=body.page_context,
            ):
                yield f"data: {json.dumps(event)}\n\n"
            # Intentional explicit commit: SSE streaming generator outlives the
            # get_session() context manager, so the auto-commit in the dependency
            # fires before streaming completes. We commit here to persist
            # conversation data after the full stream has been sent.
            await session.commit()
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/conversations", response_model=list[ChatConversationOut])
async def list_conversations(session: AsyncSession = Depends(get_session)):
    """Return all conversations ordered by most recently updated, with message counts."""
    result = await session.execute(
        select(
            ChatConversation,
            func.count(ChatMessage.id).label("message_count"),
        )
        .outerjoin(ChatMessage, ChatMessage.conversation_id == ChatConversation.id)
        .group_by(ChatConversation.id)
        .order_by(ChatConversation.updated_at.desc())
    )
    rows = result.all()
    out = []
    for conv, count in rows:
        item = ChatConversationOut.model_validate(conv)
        item.message_count = count
        out.append(item)
    return out


@router.get("/conversations/{conversation_id}", response_model=ChatConversationDetailOut)
async def get_conversation(
    conversation_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Return a single conversation with all its messages."""
    result = await session.execute(
        select(ChatConversation)
        .options(selectinload(ChatConversation.messages))
        .where(ChatConversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    item = ChatConversationDetailOut.model_validate(conv)
    item.message_count = len(conv.messages)
    return item


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a conversation and all its messages (CASCADE)."""
    await session.execute(
        delete(ChatConversation).where(ChatConversation.id == conversation_id)
    )
