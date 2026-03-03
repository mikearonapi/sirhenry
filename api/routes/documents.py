from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import DocumentListOut, DocumentOut
from pipeline.db import count_documents, get_all_documents
from pipeline.db.schema import Document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListOut)
async def list_documents(
    document_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    items = await get_all_documents(
        session,
        document_type=document_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    total = await count_documents(session, document_type=document_type, status=status)
    return DocumentListOut(
        total=total,
        items=[DocumentOut.model_validate(d) for d in items],
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut.model_validate(doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a document record. Associated transactions are NOT deleted."""
    from sqlalchemy import select
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.execute(sql_delete(Document).where(Document.id == document_id))
    await session.flush()
