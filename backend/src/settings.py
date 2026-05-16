from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Servicios externos ---
    gemini_api_key: str
    openai_api_key: str
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str = "mentor_ia_aprendizaje"
    make_webhook_url: str | None = None

    # --- Storage local ---
    base_docs_dir: Path = Path("./data/ejemplos")

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Modelos Gemini (embeddings) ---
    # Migrado a gemini-embedding-2 el 2026-05-15 porque gemini-embedding-001
    # del tier gratuito alcanzó el límite RPD 1000 durante las pruebas E2E.
    # gemini-embedding-2 tiene bucket de cuota separado y MRL nativo a 768.
    # Si vuelve a quedar limitante en producción, ver CLAUDE.md §2.5 plan B
    # (text-embedding-3-large de OpenAI).
    embedding_model: str = "gemini-embedding-2"
    embedding_output_dimensionality: int = 768
    embedding_dim: int = 768

    # --- Modelos OpenAI (LLM + OCR multimodal) ---
    openai_chat_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o-mini"

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
