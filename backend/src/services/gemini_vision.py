"""OCR multimodal con Gemini Flash para imágenes y páginas PDF renderizadas."""

from __future__ import annotations

import asyncio

from google import genai
from google.genai import types as gtypes

from src.settings import Settings

_OCR_PROMPT = (
    "Extrae todo el texto presente en esta imagen. "
    "Devuelve únicamente el texto extraído, sin comentarios ni metainformación. "
    "Preserva saltos de línea originales."
)


class GeminiVisionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)

    async def extract_text_from_image(self, image_bytes: bytes, mime: str) -> str:
        part = gtypes.Part.from_bytes(data=image_bytes, mime_type=mime)
        return await self._extract(part)

    async def extract_text_from_pdf_page(self, image_bytes: bytes) -> str:
        part = gtypes.Part.from_bytes(data=image_bytes, mime_type="image/png")
        return await self._extract(part)

    async def _extract(self, image_part: gtypes.Part) -> str:
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._settings.llm_model,
            contents=[
                gtypes.Content(
                    role="user",
                    parts=[
                        gtypes.Part.from_text(text=_OCR_PROMPT),
                        image_part,
                    ],
                )
            ],
        )
        return (response.text or "").strip()

