from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    # Embeddings
    embedding_provider: str = "disabled"  # "openai", "local", or "disabled"
    openai_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"  # OpenAI model
    local_embedding_model: str = "all-MiniLM-L6-v2"  # sentence-transformers
    max_embedding_batch_size: int = 100
    openai_embedding_cost_per_1m_tokens: Optional[float] = None

    # Database
    # Keep the no-.env fallback aligned with the default local vault profile.
    database_url: str = "sqlite+aiosqlite:///./dma-abomination-vaults.db"
    obsidian_vault_path: str = "./obsidian-abomination-vaults-vault"
    dma_private_data_root: str = "./assets/imports/misc/private-local"
    dma_campaign_id: str = "abomination-vaults"
    reference_pdf_root: str = "./assets/imports/misc/private-local/reference/raw"
    dungeon_map_root: str = "./assets/imports/misc/private-local/media"
    dungeon_room_key_root: str = "./assets/imports/misc/private-local/room-keys"

    # Text-to-speech
    # "browser" uses the frontend Web Speech API. "piper" calls a local Piper binary.
    tts_provider: str = "browser"
    piper_binary_path: str = "piper"
    piper_voice_path: Optional[str] = None
    piper_speaker_id: Optional[int] = None
    piper_length_scale: Optional[float] = None
    piper_noise_scale: Optional[float] = None
    piper_noise_w: Optional[float] = None

    # App & logging
    app_env: str = "development"
    debug: bool = Field(default=True)
    log_level: str = "INFO"
    log_file: str = "logs/dma.log"
    metrics_latency_samples: int = 500

    # CORS (future API)
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
        ]
    )

    # MapTool integration
    maptool_base_url: str = "http://localhost:5000/api"
    maptool_username: Optional[str] = None
    maptool_password: Optional[str] = None
    maptool_timeout_seconds: float = 10.0
    maptool_max_retries: int = 3

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_value(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {
                "release",
                "prod",
                "production",
                "false",
                "0",
                "off",
                "no",
            }:
                return False
            if normalized in {"dev", "development", "true", "1", "on", "yes"}:
                return True
        return value


settings = Settings()
