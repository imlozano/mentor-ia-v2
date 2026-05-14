"""Cliente de Google Cloud Vision para OCR.

Usa la REST API (`images:annotate`) en lugar del cliente gRPC oficial para
mantener la imagen del backend mínima y evitar tener que instalar grpc en
runtime. La autenticación se hace con un access token derivado del service
account JSON (path en settings.google_vision_key_json_path).
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any

import httpx
from google.auth.transport.requests import Request as GAuthRequest
from google.oauth2 import service_account
from loguru import logger

from src.settings import Settings

VISION_URL = "https://vision.googleapis.com/v1/images:annotate"
SCOPES = ["https://www.googleapis.com/auth/cloud-vision"]


class VisionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._creds_path: Path = settings.google_vision_key_json_path
        self._creds: service_account.Credentials | None = None
        self._client = httpx.AsyncClient(timeout=20.0)

    def _load_credentials(self) -> service_account.Credentials:
        if self._creds is not None:
            return self._creds
        if not self._creds_path.exists():
            raise FileNotFoundError(
                f"Credencial Vision no encontrada en {self._creds_path}"
            )
        creds = service_account.Credentials.from_service_account_file(
            str(self._creds_path), scopes=SCOPES
        )
        self._creds = creds
        return creds

    async def _access_token(self) -> str:
        creds = self._load_credentials()
        # google-auth refresca tokens de forma síncrona; lo movemos a un thread
        # para no bloquear el loop. Solo refresca si está expirado.
        if not creds.valid or (creds.expiry and creds.expiry.timestamp() < time.time() + 60):
            await asyncio.to_thread(creds.refresh, GAuthRequest())
        assert creds.token is not None
        return creds.token

    async def ocr(self, image_bytes: bytes, mime: str) -> str:
        """Extrae texto con DOCUMENT_TEXT_DETECTION. Devuelve string vacío si no hay texto."""
        token = await self._access_token()
        payload: dict[str, Any] = {
            "requests": [
                {
                    "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                }
            ]
        }
        response = await self._client.post(
            VISION_URL,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
        responses = data.get("responses") or []
        if not responses:
            return ""
        annotation = responses[0].get("fullTextAnnotation") or {}
        text = annotation.get("text", "")
        logger.debug("vision: ocr mime={} bytes={} chars_out={}", mime, len(image_bytes), len(text))
        return text

    async def close(self) -> None:
        await self._client.aclose()
