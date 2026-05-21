"""Identificadores estables de documento indexado."""

from __future__ import annotations

import uuid
from pathlib import Path

DOCUMENT_ID_NAMESPACE = uuid.NAMESPACE_URL


def compute_document_id(session_id: str, nombre_archivo: str) -> str:
    """UUIDv5 estable por sesión + nombre de archivo normalizado."""
    return str(uuid.uuid5(DOCUMENT_ID_NAMESPACE, f"{session_id}|{nombre_archivo}"))


def normalize_source_path(source_path: str) -> str:
    """Ruta canónica relativa para evitar duplicados por formato."""
    name = Path(source_path.replace("\\", "/")).name
    if not name:
        return source_path
    return f"./data/uploads/{name}"


def derive_document_id(payload: dict, session_id: str | None) -> str | None:
    """Resuelve document_id desde payload; compatible con chunks legacy."""
    raw = payload.get("document_id")
    if raw:
        return str(raw)
    if not session_id:
        return None
    nombre = str(payload.get("nombre_archivo") or "")
    if nombre:
        return compute_document_id(session_id, nombre)
    source_path = str(payload.get("source_path") or "")
    if not source_path:
        return None
    return compute_document_id(session_id, Path(source_path).name)
