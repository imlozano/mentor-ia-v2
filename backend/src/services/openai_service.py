"""Wrapper del SDK openai para Mentor IA.

Sustituye completamente a Gemini tras la activación del plan B descrito en
CLAUDE.md §2.5 (gemini-embedding-2 también agotó la cuota free de 1000 RPD
durante el despliegue inicial). Ahora absolutamente todo el LLM, OCR y
embeddings va por OpenAI.

Operaciones públicas:
- generate(prompt, system?): chat completion en gpt-4o-mini.
- extract_text_from_image(bytes, mime): OCR multimodal.
- extract_text_from_pdf_page(bytes): alias para páginas PDF renderizadas.
- embed_query(text) / embed_texts([text]): embeddings con
  text-embedding-3-large recortado a 768 dims (MRL nativo) y renormalizado
  a norma unitaria — compatible con la colección Qdrant COSINE existente.
- ping(timeout): models.retrieve del chat model (no consume tokens).
"""

from __future__ import annotations

import asyncio
import base64
import math
import re
from typing import Sequence

from loguru import logger
from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from src.settings import Settings

_OCR_PROMPT = (
    "Extrae todo el texto presente en esta imagen. "
    "Devuelve únicamente el texto extraído, sin comentarios ni metainformación. "
    "Preserva saltos de línea originales."
)


class OpenAIService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    # ----- Generación de texto -----

    async def generate(
        self, prompt: str, system: str | None = None, max_tokens: int | None = None
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        attempts = 3
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self._settings.openai_chat_model,
                    messages=messages,  # type: ignore[arg-type]
                    max_tokens=max_tokens,
                )
                text = response.choices[0].message.content or ""
                return text.strip()
            except (RateLimitError, APITimeoutError, APIError) as exc:
                last_exc = exc
                if attempt >= attempts:
                    raise
                wait_s = self._retry_wait_seconds(str(exc), attempt)
                logger.warning(
                    "openai generate transient error; reintento {}/{} en {}s",
                    attempt,
                    attempts,
                    wait_s,
                )
                await asyncio.sleep(wait_s)

        assert last_exc is not None
        raise last_exc

    # ----- OCR multimodal -----

    async def extract_text_from_image(
        self, image_bytes: bytes, mime: str, max_tokens: int | None = None
    ) -> str:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"

        attempts = 4
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self._settings.openai_vision_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": _OCR_PROMPT},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        }
                    ],  # type: ignore[arg-type]
                    max_tokens=max_tokens,
                )
                text = response.choices[0].message.content or ""
                return text.strip()
            except (RateLimitError, APITimeoutError, APIError) as exc:
                if attempt >= attempts:
                    raise
                wait_s = self._retry_wait_seconds(str(exc), attempt)
                logger.warning(
                    "openai vision transient error; reintento {}/{} en {}s",
                    attempt,
                    attempts,
                    wait_s,
                )
                await asyncio.sleep(wait_s)
        return ""

    async def extract_text_from_pdf_page(
        self, image_bytes: bytes, max_tokens: int | None = None
    ) -> str:
        return await self.extract_text_from_image(
            image_bytes, mime="image/png", max_tokens=max_tokens
        )

    # ----- Embeddings -----

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        attempts = 3
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.embeddings.create(
                    model=self._settings.openai_embedding_model,
                    input=list(texts),
                    dimensions=self._settings.openai_embedding_dimensions,
                )
                # text-embedding-3-* con `dimensions` truncado (MRL) NO
                # garantiza norma unitaria; renormalizamos para preservar la
                # propiedad que Qdrant COSINE espera.
                return [self._normalize(list(item.embedding)) for item in response.data]
            except (RateLimitError, APITimeoutError, APIError) as exc:
                last_exc = exc
                if attempt >= attempts:
                    raise
                wait_s = self._retry_wait_seconds(str(exc), attempt)
                logger.warning(
                    "openai embeddings transient error; reintento {}/{} en {}s",
                    attempt,
                    attempts,
                    wait_s,
                )
                await asyncio.sleep(wait_s)

        assert last_exc is not None
        raise last_exc

    # ----- Health -----

    async def ping(self, timeout: float = 2.0) -> bool:
        """models.retrieve no consume tokens. Devuelve True/False."""
        try:
            await asyncio.wait_for(
                self._client.models.retrieve(self._settings.openai_chat_model),
                timeout=timeout,
            )
            return True
        except Exception as exc:  # noqa: BLE001 — health check, swallow all
            logger.warning("openai ping failed: {!r}", exc)
            return False

    async def close(self) -> None:
        await self._client.close()

    # ----- Internos -----

    @staticmethod
    def _normalize(vec: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            return vec
        return [x / norm for x in vec]

    @staticmethod
    def _retry_wait_seconds(message: str, attempt: int) -> int:
        match = re.search(r"retry[-\s]?after[:\s]+([0-9]+(?:\.[0-9]+)?)", message, re.IGNORECASE)
        if match:
            return max(1, int(float(match.group(1))) + 1)
        if "rate" in message.lower() or "429" in message:
            return min(60, 15 * attempt)
        return 2 * attempt
