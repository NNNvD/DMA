from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from backend.config.settings import settings
from backend.models.base import init_db
from backend.services.scheduler import scheduler
from backend.api.routes.documents import router as documents_router
from backend.api.routes.admin import router as admin_router
from backend.api.routes.context import router as context_router
from backend.api.errors import install_exception_handlers


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DMA API")
    await init_db()
    logger.info("DB initialized")
    scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()
        logger.info("DMA API shutdown complete")


app = FastAPI(title="DMA API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_exception_handlers(app)


@app.middleware("http")
async def rate_limit_headers(request, call_next):
    # Simple placeholder headers; replace with real limiter as needed
    response: Response = await call_next(request)
    response.headers.setdefault("X-RateLimit-Limit", "60")
    response.headers.setdefault("X-RateLimit-Remaining", "60")
    return response


@app.get("/")
async def root():
    return {"message": "DMA API", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Routers
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(context_router, prefix="/api/context", tags=["context"])
