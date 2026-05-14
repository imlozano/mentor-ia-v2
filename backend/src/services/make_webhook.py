"""Cliente del webhook de Make.com.

Hace POST con el payload del plan de repaso. Devuelve True si la respuesta
es 2xx (Make.com responde antes de que Gmail Sender termine, así que True
significa "Make recibió el plan", no "el correo llegó").
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from src.settings import Settings


class MakeWebhookService:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.make_webhook_url
        self._client = httpx.AsyncClient(timeout=10.0)

    async def enviar_plan(self, payload: dict[str, Any]) -> bool:
        if not self._url:
            logger.warning("make_webhook: MAKE_WEBHOOK_URL no configurada, omitiendo envío")
            return False
        try:
            response = await self._client.post(self._url, json=payload)
        except httpx.HTTPError as exc:
            logger.error("make_webhook: error en POST: {!r}", exc)
            return False

        ok = 200 <= response.status_code < 300
        if not ok:
            logger.error(
                "make_webhook: respuesta no-2xx status={} body={!r}",
                response.status_code,
                response.text[:200],
            )
        return ok

    async def close(self) -> None:
        await self._client.aclose()
