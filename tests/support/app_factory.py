import asyncio

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.routes.admin import router as admin_router
from backend.api.routes.campaign import router as campaign_router
from backend.api.routes.documents import router as documents_router
from backend.api.routes.prep import router as prep_router
from backend.models.base import Base, get_db
import backend.models.campaign  # noqa: F401
import backend.models.document  # noqa: F401


def create_documents_test_app():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session_local = asyncio.run(_init())
    app = FastAPI()
    app.include_router(documents_router, prefix="/api/documents")
    app.include_router(admin_router, prefix="/api/admin")
    app.include_router(campaign_router, prefix="/api/campaign")
    app.include_router(prep_router, prefix="/api/prep")

    async def override_get_db():
        async with session_local() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, engine, session_local
