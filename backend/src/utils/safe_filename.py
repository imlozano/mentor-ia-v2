"""Sanitización de nombres de archivo subidos por el usuario.

Defensas:
- Elimina componentes de path (`..`, `/`, `\\`) → previene path traversal.
- Solo conserva [A-Za-z0-9._-]; el resto se sustituye por `_`.
- Colapsa underscores consecutivos.
- Quita puntos iniciales (evita archivos ocultos tipo `.env`).
- Trunca a 200 caracteres preservando la extensión.
- Si tras sanitizar queda vacío, devuelve `archivo_sin_nombre`.
"""

from __future__ import annotations

import re
from pathlib import PurePath

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_UNDERSCORE = re.compile(r"_+")
_MAX_LEN = 200


def safe_filename(nombre_original: str) -> str:
    # PurePath.name descarta cualquier componente de path (Windows o POSIX).
    base = PurePath(nombre_original).name if nombre_original else ""

    cleaned = _UNSAFE.sub("_", base)
    cleaned = _REPEATED_UNDERSCORE.sub("_", cleaned)
    cleaned = cleaned.lstrip(".").strip("_")

    if not cleaned:
        return "archivo_sin_nombre"

    if len(cleaned) > _MAX_LEN:
        p = PurePath(cleaned)
        suffix = p.suffix[:10]  # extensión máx. 10 chars
        stem = p.stem
        cleaned = stem[: _MAX_LEN - len(suffix)] + suffix

    return cleaned


if __name__ == "__main__":
    casos = [
        "documento normal.pdf",
        "../../etc/passwd",
        "..\\..\\windows\\system32\\config.sys",
        ".env",
        "  whitespace  .txt",
        "archivo con !@#$ raros %&* chars.md",
        "",
        "a" * 250 + ".pdf",
        "evil/../traversal.pdf",
    ]
    for c in casos:
        print(f"{c!r:60} -> {safe_filename(c)!r}")
