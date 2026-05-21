"""Utilidades para archivos subidos en ``upload_dir``."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.settings import Settings
from src.utils.safe_filename import safe_filename


def resolve_upload_path(settings: Settings, nombre_archivo: str) -> Path:
    """Ruta canónica bajo ``upload_dir`` para un nombre de archivo."""
    return settings.upload_dir / safe_filename(nombre_archivo)


def unlink_upload(settings: Settings, nombre_archivo: str) -> bool:
    """Elimina el archivo local si existe. No lanza si falta."""
    path = resolve_upload_path(settings, nombre_archivo)
    if not path.exists():
        return False
    try:
        path.unlink()
        logger.info("upload: archivo local eliminado {!r}", path)
        return True
    except OSError as exc:
        logger.warning("upload: no se pudo eliminar {!r}: {!r}", path, exc)
        return False
