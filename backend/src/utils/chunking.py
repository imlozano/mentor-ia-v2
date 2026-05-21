"""Chunking de texto para indexación.

Expone dos estrategias:

- ``chunkear``: trocea por caracteres con solape, para PDF/TXT/imágenes.
- ``chunkear_markdown``: respeta los encabezados Markdown (H1-H3) como
  fronteras naturales, luego aplica ``chunkear`` si una sección es demasiado
  grande. Produce chunks semánticamente más coherentes para documentos .md.

Los parámetros por defecto (900 / 150 / 100) son los del proyecto y están
justificados en docs/academic/Modelo_Datos_Qdrant.md §3.
"""

from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^#{1,3}\s", re.MULTILINE)
_MIN_SECTION_CHARS = 80  # Secciones más cortas se fusionan con la siguiente


def chunkear(
    texto: str,
    max_chars: int = 900,
    overlap: int = 150,
    max_chunks: int = 100,
) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars debe ser > 0")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap debe estar en [0, max_chars)")
    if max_chunks <= 0:
        raise ValueError("max_chunks debe ser > 0")

    if not texto or not texto.strip():
        return []

    stride = max_chars - overlap
    chunks: list[str] = []
    pos = 0
    n = len(texto)

    while pos < n and len(chunks) < max_chunks:
        end = min(pos + max_chars, n)
        piece = texto[pos:end].strip()
        if piece:
            chunks.append(piece)
        if end == n:
            break
        pos += stride

    return chunks


def chunkear_markdown(
    texto: str,
    max_chars: int = 900,
    overlap: int = 150,
    max_chunks: int = 100,
) -> list[str]:
    """Chunking que respeta fronteras de encabezados Markdown.

    Divide el texto por encabezados H1-H3 para que cada chunk corresponda
    a una sección coherente.  Si una sección excede ``max_chars``, se
    subdivide con ``chunkear``.  Secciones muy cortas (< ``_MIN_SECTION_CHARS``)
    se fusionan con la siguiente para evitar micro-chunks.

    El total de chunks producidos no supera ``max_chunks``.
    """
    if not texto or not texto.strip():
        return []

    # Dividir por encabezados preservando el encabezado con su sección
    parts = _HEADING_RE.split(texto)
    headers = _HEADING_RE.findall(texto)

    # Reconstruir secciones: primer parte puede ser preámbulo sin encabezado
    sections: list[str] = []
    if parts[0].strip():
        sections.append(parts[0].strip())
    for header, body in zip(headers, parts[1:]):
        sections.append((header + body).strip())

    # Fusionar secciones muy cortas con la siguiente
    merged: list[str] = []
    buffer = ""
    for sec in sections:
        if buffer:
            buffer = buffer + "\n\n" + sec
            if len(buffer) >= _MIN_SECTION_CHARS:
                merged.append(buffer)
                buffer = ""
        elif len(sec) < _MIN_SECTION_CHARS:
            buffer = sec
        else:
            merged.append(sec)
    if buffer:
        if merged:
            merged[-1] = merged[-1] + "\n\n" + buffer
        else:
            merged.append(buffer)

    # Subdividir secciones grandes y aplanar a lista final
    chunks: list[str] = []
    for sec in merged:
        if len(chunks) >= max_chunks:
            break
        remaining = max_chunks - len(chunks)
        if len(sec) <= max_chars:
            chunks.append(sec)
        else:
            sub = chunkear(sec, max_chars=max_chars, overlap=overlap, max_chunks=remaining)
            chunks.extend(sub)

    return chunks[:max_chunks]


if __name__ == "__main__":
    sample = "ipsum lorem " * 200  # ~2400 chars
    out = chunkear(sample)
    print(f"input chars: {len(sample)}")
    print(f"num chunks:  {len(out)}")
    print(f"chunk 0 len: {len(out[0])}")
    print(f"chunk 0 head: {out[0][:60]!r}")
    print(f"chunk 1 head: {out[1][:60]!r}")
    print(
        f"overlap entre chunk 0 y chunk 1 detectable: {out[0][-60:].split() != out[1][:60].split()}"
    )
