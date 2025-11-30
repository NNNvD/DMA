import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from backend.config.settings import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

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
    async with engine.begin() as conn:
        logger.info("Initializing DMA database tables…")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("DMA database initialized")


async def get_db() -> AsyncSession:
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

