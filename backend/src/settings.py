from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Servicios externos ---
    openai_api_key: str
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str = "mentor_ia_aprendizaje"
    make_webhook_url: str | None = None

    # --- Storage local ---
    base_docs_dir: Path = Path("./data/ejemplos")

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Modelos OpenAI ---
    # Plan B activado el 2026-05-17 (gemini-embedding-2 también agotó cuota
    # free 1000 RPD durante despliegue inicial). Ver CLAUDE.md §2.5.
    # text-embedding-3-large soporta MRL nativo vía parámetro `dimensions`;
    # OpenAIService renormaliza a norma unitaria para preservar COSINE.
    openai_chat_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-large"
    openai_embedding_dimensions: int = 768

    # Dimensión que se guarda en el payload Qdrant para auditoría.
    embedding_dim: int = 768

    # --- Chunking ---
    chunk_max_chars: int = 900
    chunk_overlap: int = 150
    chunk_max: int = 100

    # --- RAG ---
    rag_score_threshold: float = 0.55
    rag_top_k: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
