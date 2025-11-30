from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.models.base import get_db
from backend.models.document import Document
from backend.services.embedding_service import embedding_service


router = APIRouter()


class DocumentCreate(BaseModel):
    title: str
    kind: str
    content: Optional[str] = None
    summary: Optional[str] = None
    source_name: Optional[str] = None
    url: Optional[str] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    kind: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    source_name: Optional[str] = None
    url: Optional[str] = None
    refresh_embedding: Optional[bool] = None


def _to_dict(d: Document):
    return {
        "id": d.id,
        "title": d.title,
        "kind": d.kind,
        "content": d.content,
        "summary": d.summary,
        "source_name": d.source_name,
        "url": d.url,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        "has_embedding": bool(d.embedding),
    }


@router.get("")
async def list_documents(
    kind: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    base = select(Document)
    count_stmt = select(func.count(Document.id))
    if kind:
        base = base.where(Document.kind == kind)
        count_stmt = count_stmt.where(Document.kind == kind)
    if q:
        ilike = f"%{q}%"
        cond = (Document.title.ilike(ilike)) | (Document.content.ilike(ilike))
        base = base.where(cond)
        count_stmt = count_stmt.where(cond)

    # total count
    total = (await db.execute(count_stmt)).scalar() or 0
    pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    offset = (page - 1) * page_size

    stmt = base.order_by(Document.updated_at.desc()).offset(offset).limit(page_size)
    res = await db.execute(stmt)
    docs = res.scalars().all()
    payload = PaginatedResponse(
        items=[_to_dict(d) for d in docs], total=total, page=page, page_size=page_size, pages=pages
    ).model_dump()
    return payload


@router.get("/{doc_id}")
async def get_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_dict(doc)


@router.post("")
async def create_document(payload: DocumentCreate, db: AsyncSession = Depends(get_db)):
    doc = Document(
        title=payload.title,
        kind=payload.kind,
        content=payload.content,
        summary=payload.summary,
        source_name=payload.source_name,
        url=payload.url,
    )
    db.add(doc)
    await db.flush()

    # Optionally compute embedding
    if embedding_service.provider != "disabled":
        text = embedding_service.create_document_text(doc.__dict__)
        emb = await embedding_service.generate_embedding(text)
        if emb:
            doc.embedding = emb

    await db.commit()
    await db.refresh(doc)
    return _to_dict(doc)


@router.patch("/{doc_id}")
async def update_document(doc_id: int, payload: DocumentUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    changed_fields = []
    for field, value in payload.model_dump(exclude_unset=True, exclude={"refresh_embedding"}).items():
        setattr(doc, field, value)
        changed_fields.append(field)

    # Recompute embedding when relevant fields changed or explicitly requested
    should_refresh = payload.refresh_embedding or any(f in changed_fields for f in ("title", "summary", "content", "kind", "source_name"))
    if should_refresh and embedding_service.provider != "disabled":
        text = embedding_service.create_document_text(doc.__dict__)
        emb = await embedding_service.generate_embedding(text)
        if emb:
            doc.embedding = emb

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int

    await db.commit()
    await db.refresh(doc)
    return _to_dict(doc)


@router.delete("/{doc_id}")
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.commit()
    return {"deleted": True, "id": doc_id}
