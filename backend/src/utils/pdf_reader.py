"""Extracción de texto desde PDFs usando pypdf.

Concatena el texto de cada página con doble newline. Páginas sin texto
(ej. PDFs escaneados sin capa OCR) se omiten silenciosamente; si el
PDF entero no tiene texto extraíble, devuelve string vacío y quien lo
llama decide qué hacer (típicamente: sugerir OCR al usuario).
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extraer_texto_pdf_por_paginas(path: Path | str) -> list[str]:
    p = Path(path)
    reader = PdfReader(str(p))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def extraer_texto_pdf(path: Path | str) -> str:
    pages = extraer_texto_pdf_por_paginas(path)
    return "\n\n".join([text for text in pages if text])


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("uso: python -m src.utils.pdf_reader <ruta_al_pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    texto = extraer_texto_pdf(pdf_path)
    print(f"archivo: {pdf_path}")
    print(f"caracteres extraídos: {len(texto)}")
    if texto:
        print(f"primeros 400 chars:\n{texto[:400]}")
    else:
        print("(sin texto extraíble; probablemente PDF escaneado, usar OCR)")
