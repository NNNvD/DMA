from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # Embeddings
    embedding_provider: str = "disabled"  # "openai", "local", or "disabled"
    openai_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"  # OpenAI model
    local_embedding_model: str = "all-MiniLM-L6-v2"  # sentence-transformers
    max_embedding_batch_size: int = 100

    # Database
    database_url: str = "sqlite+aiosqlite:///./dma.db"

    # App & logging
    app_env: str = "development"
    debug: bool = Field(default=True)
    log_level: str = "INFO"
    log_file: str = "logs/dma.log"

    # CORS (future API)
    cors_origins: List[str] = Field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:5173",
    ])


settings = Settings()

