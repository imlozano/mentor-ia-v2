"""Chunking de texto para indexación.

Trocea un texto en bloques de hasta `max_chars` caracteres con `overlap`
caracteres de solape entre bloques consecutivos, hasta un tope de
`max_chunks` chunks por documento.

Los parámetros por defecto (900 / 150 / 100) son los del proyecto y están
justificados en docs/academic/Modelo_Datos_Qdrant.md §3.
"""

from __future__ import annotations


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
