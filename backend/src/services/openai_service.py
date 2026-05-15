"""Wrapper del SDK openai para Mentor IA.

Sustituye a Gemini para LLM y OCR multimodal por restricción de cuota del
tier gratuito de Gemini (20 RPD). Embeddings siguen en Gemini (ver §2.5 de
CLAUDE.md).

Tres operaciones públicas:
- generate(prompt, system?): chat completion en gpt-4o-mini.
- extract_text_from_image(bytes, mime): OCR multimodal con la misma firma
  que tenía GeminiVisionService para minimizar cambios en los agentes.
- extract_text_from_pdf_page(bytes): alias de extract_text_from_image para
  páginas de PDF renderizadas a PNG.
- ping(timeout): models.retrieve, sin consumir tokens.
"""

from __future__ import annotations

import asyncio
import base64
import re

from loguru import logger
from openai import AsyncOpenAI
from openai import APIError, APITimeoutError, RateLimitError

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

    async def generate(self, prompt: str, system: str | None = None) -> str:
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

    async def extract_text_from_image(self, image_bytes: bytes, mime: str) -> str:
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

    async def extract_text_from_pdf_page(self, image_bytes: bytes) -> str:
        return await self.extract_text_from_image(image_bytes, mime="image/png")

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
    def _retry_wait_seconds(message: str, attempt: int) -> int:
        match = re.search(r"retry[-\s]?after[:\s]+([0-9]+(?:\.[0-9]+)?)", message, re.IGNORECASE)
        if match:
            return max(1, int(float(match.group(1))) + 1)
        if "rate" in message.lower() or "429" in message:
            return min(60, 15 * attempt)
        return 2 * attempt
