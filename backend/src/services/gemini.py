"""Wrapper del SDK google-genai para Mentor IA.

Provee tres operaciones:
- embed_query / embed_texts: vectores de 768 dim renormalizados a norma 1.
- generate: respuesta de texto del LLM.
- ping: verificación liviana para /health.

Sobre la renormalización: `gemini-embedding-001` con `outputDimensionality=768`
trunca un vector original de 3072 dimensiones aplicando Matryoshka
Representation Learning. El vector truncado pierde la norma unitaria (norma
empírica ≈ 0.57). Como la métrica COSINE en Qdrant trabaja óptimamente con
vectores unitarios, renormalizamos antes de devolver.
"""

from __future__ import annotations

import asyncio
import math
from typing import Sequence

from google import genai
from google.genai import types as gtypes
from loguru import logger

from src.settings import Settings


class GeminiService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)

    # ----- Embeddings -----

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        config = gtypes.EmbedContentConfig(
            output_dimensionality=self._settings.embedding_output_dimensionality,
        )

        # El SDK de google-genai es síncrono en este endpoint; lo movemos a
        # un thread para no bloquear el loop async de FastAPI.
        response = await asyncio.to_thread(
            self._client.models.embed_content,
            model=self._settings.embedding_model,
            contents=list(texts),
            config=config,
        )

        return [self._normalize(list(e.values)) for e in response.embeddings]

    # ----- Generación de texto -----

    async def generate(self, prompt: str, system: str | None = None) -> str:
        config = gtypes.GenerateContentConfig(system_instruction=system) if system else None

        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._settings.llm_model,
            contents=prompt,
            config=config,
        )

        text = response.text or ""
        return text.strip()

    # ----- Health -----

    async def ping(self, timeout: float = 2.0) -> bool:
        """Verifica conectividad con un embed liviano. Devuelve True/False."""
        try:
            await asyncio.wait_for(self.embed_query("ping"), timeout=timeout)
            return True
        except Exception as exc:  # noqa: BLE001 — health check, swallow all
            logger.warning("gemini ping failed: {!r}", exc)
            return False

    # ----- Internos -----

    @staticmethod
    def _normalize(vec: list[float]) -> list[float]:
        """Renormaliza un vector a norma euclídea 1.

        Necesario tras truncar con outputDimensionality (MRL): los embeddings
        truncados pierden la norma unitaria y degradan COSINE en Qdrant.
        """
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            return vec
        return [x / norm for x in vec]
