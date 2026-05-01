from typing import Any, List, Optional
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from backend.models.base import get_db
from backend.models.document import Document
from backend.services.ingestion_governance import (
    PrivacyScope,
    ReviewStatus,
    SourceClass,
    VisibilityScope,
)
from backend.services.ingestion_service import ingestion_service
from backend.services.metrics_service import metrics_service
from backend.services.retrieval_service import retrieval_service
from backend.services.rules_service import rules_service


router = APIRouter()


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int


class DocumentCreate(BaseModel):
    title: str
    kind: str
    content: Optional[str] = None
    summary: Optional[str] = None
    source_name: Optional[str] = None
    url: Optional[str] = None
    source_class: SourceClass = SourceClass.private_local
    privacy_scope: PrivacyScope = PrivacyScope.private_local
    review_status: ReviewStatus = ReviewStatus.approved
    visibility_scope: VisibilityScope = VisibilityScope.gm_only
    rag_eligible: bool = True
    train_eligible: bool = False


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    kind: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    source_name: Optional[str] = None
    url: Optional[str] = None
    source_class: Optional[SourceClass] = None
    privacy_scope: Optional[PrivacyScope] = None
    review_status: Optional[ReviewStatus] = None
    visibility_scope: Optional[VisibilityScope] = None
    rag_eligible: Optional[bool] = None
    train_eligible: Optional[bool] = None
    refresh_embedding: Optional[bool] = None


class RulesQueryRequest(BaseModel):
    query: str
    top_k: int = 3
    strict: bool = False


class SearchQueryResponse(BaseModel):
    query: str
    results: List[Any]


def _to_dict(d: Document):
    return {
        "id": d.id,
        "title": d.title,
        "kind": d.kind,
        "content": d.content,
        "summary": d.summary,
        "source_name": d.source_name,
        "url": d.url,
        "source_class": d.source_class,
        "privacy_scope": d.privacy_scope,
        "review_status": d.review_status,
        "visibility_scope": d.visibility_scope,
        "rag_eligible": d.rag_eligible,
        "train_eligible": d.train_eligible,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        "has_embedding": bool(d.embedding),
    }


def _apply_document_filters(
    stmt,
    *,
    kind: Optional[str] = None,
    q: Optional[str] = None,
    source_class: Optional[SourceClass] = None,
    privacy_scope: Optional[PrivacyScope] = None,
    review_status: Optional[ReviewStatus] = None,
    visibility_scope: Optional[VisibilityScope] = None,
    rag_eligible: Optional[bool] = None,
    train_eligible: Optional[bool] = None,
):
    if kind:
        stmt = stmt.where(Document.kind == kind)
    if source_class:
        stmt = stmt.where(Document.source_class == source_class.value)
    if privacy_scope:
        stmt = stmt.where(Document.privacy_scope == privacy_scope.value)
    if review_status:
        stmt = stmt.where(Document.review_status == review_status.value)
    if visibility_scope:
        stmt = stmt.where(Document.visibility_scope == visibility_scope.value)
    if rag_eligible is not None:
        stmt = stmt.where(Document.rag_eligible == rag_eligible)
    if train_eligible is not None:
        stmt = stmt.where(Document.train_eligible == train_eligible)
    if q:
        ilike = f"%{q}%"
        stmt = stmt.where(
            (Document.title.ilike(ilike)) | (Document.content.ilike(ilike))
        )
    return stmt


@router.get("")
async def list_documents(
    kind: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    source_class: Optional[SourceClass] = Query(default=None),
    privacy_scope: Optional[PrivacyScope] = Query(default=None),
    review_status: Optional[ReviewStatus] = Query(default=None),
    visibility_scope: Optional[VisibilityScope] = Query(default=None),
    rag_eligible: Optional[bool] = Query(default=None),
    train_eligible: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    base = _apply_document_filters(
        select(Document),
        kind=kind,
        q=q,
        source_class=source_class,
        privacy_scope=privacy_scope,
        review_status=review_status,
        visibility_scope=visibility_scope,
        rag_eligible=rag_eligible,
        train_eligible=train_eligible,
    )
    count_stmt = _apply_document_filters(
        select(func.count(Document.id)),
        kind=kind,
        q=q,
        source_class=source_class,
        privacy_scope=privacy_scope,
        review_status=review_status,
        visibility_scope=visibility_scope,
        rag_eligible=rag_eligible,
        train_eligible=train_eligible,
    )

    # total count
    total = (await db.execute(count_stmt)).scalar() or 0
    pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    offset = (page - 1) * page_size

    stmt = base.order_by(Document.updated_at.desc()).offset(offset).limit(page_size)
    res = await db.execute(stmt)
    docs = res.scalars().all()
    payload = PaginatedResponse(
        items=[_to_dict(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    ).model_dump()
    return payload


@router.get("/search", response_model=SearchQueryResponse)
async def search_documents(
    q: str = Query(min_length=1),
    kind: Optional[str] = Query(default=None),
    source_class: Optional[SourceClass] = Query(default=None),
    privacy_scope: Optional[PrivacyScope] = Query(default=None),
    review_status: Optional[ReviewStatus] = Query(default=None),
    visibility_scope: Optional[VisibilityScope] = Query(default=None),
    rag_eligible: Optional[bool] = Query(default=None),
    train_eligible: Optional[bool] = Query(default=None),
    top_k: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        results = await retrieval_service.search_documents(
            q,
            db,
            top_k=top_k,
            kind=kind,
            source_class=source_class.value if source_class else None,
            privacy_scope=privacy_scope.value if privacy_scope else None,
            review_status=review_status.value if review_status else None,
            visibility_scope=visibility_scope.value if visibility_scope else None,
            rag_eligible=rag_eligible,
            train_eligible=train_eligible,
        )
        response_payload = {"query": q, "results": results}
        success = True
        return response_payload
    finally:
        metrics_service.record(
            "documents.search",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens(
                {
                    "q": q,
                    "kind": kind,
                    "source_class": source_class.value if source_class else None,
                    "privacy_scope": privacy_scope.value if privacy_scope else None,
                    "review_status": review_status.value if review_status else None,
                    "visibility_scope": (
                        visibility_scope.value if visibility_scope else None
                    ),
                    "rag_eligible": rag_eligible,
                    "train_eligible": train_eligible,
                    "top_k": top_k,
                }
            ),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.post("/rules/query")
async def query_rules(payload: RulesQueryRequest, db: AsyncSession = Depends(get_db)):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = await rules_service.answer_question(
            payload.query,
            db,
            top_k=payload.top_k,
            strict=payload.strict,
        )
        success = True
        return response_payload
    finally:
        metrics_service.record(
            "rules.query",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens(payload.model_dump()),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.get("/{doc_id}")
async def get_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_dict(doc)


@router.post("")
async def create_document(payload: DocumentCreate, db: AsyncSession = Depends(get_db)):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = _to_dict(
            await ingestion_service.ingest_document(
                db,
                title=payload.title,
                kind=payload.kind,
                content=payload.content,
                summary=payload.summary,
                source_name=payload.source_name,
                url=payload.url,
                source_class=payload.source_class.value,
                privacy_scope=payload.privacy_scope.value,
                review_status=payload.review_status.value,
                visibility_scope=payload.visibility_scope.value,
                rag_eligible=payload.rag_eligible,
                train_eligible=payload.train_eligible,
            )
        )
        success = True
        return response_payload
    finally:
        metrics_service.record(
            "documents.create",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens(
                payload.model_dump(exclude_none=True)
            ),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.patch("/{doc_id}")
async def update_document(
    doc_id: int, payload: DocumentUpdate, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == doc_id)
    )
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    changed_fields = []
    for field, value in payload.model_dump(
        mode="json", exclude_unset=True, exclude={"refresh_embedding"}
    ).items():
        setattr(doc, field, value)
        changed_fields.append(field)

    content_changed = "content" in changed_fields
    should_refresh = payload.refresh_embedding or any(
        field in changed_fields
        for field in ("title", "summary", "content", "kind", "source_name")
    )
    if should_refresh:
        await ingestion_service.refresh_document(db, doc, rechunk=content_changed)
    else:
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
