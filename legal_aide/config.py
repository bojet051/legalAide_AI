"""
Application configuration helpers.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:  # pragma: no cover
    from psycopg_pool import ConnectionPool
    from legal_aide.embeddings import EmbeddingClient


class Settings(BaseSettings):
    """Configuration loaded from environment variables."""

    database_url: str = Field(..., alias="DATABASE_URL")
    embedding_dim: int = Field(1536, alias="EMBEDDING_DIM")
    embedding_model: str = Field("text-embedding-3-large", alias="EMBEDDING_MODEL")
    embedding_api_url: str | None = Field(None, alias="EMBEDDING_API_URL")
    embedding_api_key: str | None = Field(None, alias="EMBEDDING_API_KEY")
    llm_model: str | None = Field(None, alias="LLM_MODEL")
    llm_api_url: str | None = Field(None, alias="LLM_API_URL")
    llm_api_key: str | None = Field(None, alias="LLM_API_KEY")
    chunk_token_size: int = Field(800, alias="CHUNK_TOKEN_SIZE")
    chunk_overlap_ratio: float = Field(0.15, alias="CHUNK_OVERLAP_RATIO")
    ocr_tesseract_cmd: str | None = Field(None, alias="TESSERACT_CMD")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class RuntimeContext(BaseModel):
    """Holds global singletons shared across modules."""

    settings: Settings
    embedding_client: "EmbeddingClient"
    db_pool: "ConnectionPool"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
