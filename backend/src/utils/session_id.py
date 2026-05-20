"""Validación del identificador de sesión anónimo.

Mentor IA no tiene autenticación (CLAUDE.md §2.1). Para evitar que los
documentos, consultas y planes de distintos visitantes se mezclen, el
frontend genera un UUIDv4 anónimo y lo envía en el header `X-Session-ID`.
El backend solo lo usa como clave de aislamiento en Qdrant: no es una
credencial ni identifica a una persona.
"""

from __future__ import annotations

import uuid

from fastapi import Header, HTTPException

_MAX_LEN = 36


def sanitize_session_id(raw: str | None) -> str | None:
    """Devuelve el session_id si es un UUIDv4 válido; si no, None.

    Se descarta cualquier valor que no sea UUIDv4 para impedir que un cliente
    inyecte texto arbitrario como clave de partición en Qdrant.
    """
    if not raw or len(raw) > _MAX_LEN:
        return None
    try:
        parsed = uuid.UUID(raw)
    except (ValueError, AttributeError):
        return None
    if parsed.version != 4:
        return None
    return str(parsed)


def require_session_id(
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> str:
    """Dependencia FastAPI: exige un X-Session-ID válido o responde 400."""
    session_id = sanitize_session_id(x_session_id)
    if session_id is None:
        raise HTTPException(
            status_code=400,
            detail="Falta el header 'X-Session-ID' o no es un UUIDv4 válido.",
        )
    return session_id
