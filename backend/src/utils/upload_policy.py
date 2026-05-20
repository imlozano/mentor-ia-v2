"""Política centralizada de validación de archivos subidos.

Único punto de verdad para extensiones soportadas y límites de tamaño. Tanto
los endpoints (`app.py`) como el agente de extracción importan de aquí, para
evitar que las constantes se desincronicen.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from src.settings import Settings
from src.utils.safe_filename import safe_filename

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
TEXT_EXTENSIONS = {".txt", ".md"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_UPLOAD_EXTENSIONS = IMAGE_EXTENSIONS | TEXT_EXTENSIONS | PDF_EXTENSIONS


def _limit_for_suffix(suffix: str, settings: Settings) -> int:
    if suffix in IMAGE_EXTENSIONS:
        return settings.max_image_bytes
    if suffix in PDF_EXTENSIONS:
        return settings.max_pdf_bytes
    return settings.max_text_bytes


def validate_upload(filename: str, size: int | None, settings: Settings) -> str:
    """Sanitiza el nombre y valida extensión y tamaño.

    Devuelve el nombre de archivo saneado. Lanza HTTPException(400) con un
    mensaje claro si la extensión no está soportada o el tamaño excede el
    límite del tipo. `size` puede ser None (algunos clientes no envían
    Content-Length); en ese caso el límite se verifica más tarde tras leer.
    """
    safe_name = safe_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
        mostrado = suffix or "(sin extensión)"
        permitidas = ", ".join(sorted(SUPPORTED_UPLOAD_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Extensión no soportada: '{mostrado}'. Permitidas: {permitidas}.",
        )
    limit = _limit_for_suffix(suffix, settings)
    if size is not None and size > limit:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo supera el tamaño máximo de {limit // (1024 * 1024)} MB.",
        )
    return safe_name


def enforce_size(suffix: str, content: bytes, settings: Settings) -> None:
    """Verifica el tamaño real tras leer el contenido en memoria."""
    limit = _limit_for_suffix(suffix.lower(), settings)
    if len(content) > limit:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo supera el tamaño máximo de {limit // (1024 * 1024)} MB.",
        )
