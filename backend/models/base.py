import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Create database tables for all registered models."""
    # Import models to ensure metadata is populated before create_all
    import backend.models.campaign  # noqa: F401
    import backend.models.document  # noqa: F401
    import backend.models.context  # noqa: F401
    import backend.models.chunk  # noqa: F401

    async with engine.begin() as conn:
        logger.info("Initializing DMA database tables…")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("DMA database initialized")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for request handlers/services."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
