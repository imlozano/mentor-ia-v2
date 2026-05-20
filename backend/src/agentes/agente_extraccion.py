from __future__ import annotations

import binascii
import struct
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

import pypdfium2 as pdfium
from loguru import logger
from qdrant_client.http import models as qmodels

from src.services.openai_service import OpenAIService
from src.services.qdrant_client import QdrantService
from src.settings import Settings
from src.utils.chunking import chunkear
from src.utils.pdf_reader import extraer_texto_pdf, extraer_texto_pdf_por_paginas

_SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
_PDF_SCANNED_THRESHOLD = 50


class AgenteExtraccion:
    def __init__(
        self,
        qdrant_client: QdrantService,
        openai_service: OpenAIService,
        settings: Settings,
    ) -> None:
        self._qdrant = qdrant_client
        self._openai = openai_service
        self._settings = settings
        self._id_namespace = uuid.NAMESPACE_URL

    async def ingestar_documento(self, path: Path) -> int:
        """Ingesta un documento y devuelve cantidad de chunks indexados."""
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Archivo no encontrado: {path}")

        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError(f"Extensión no soportada: {suffix}")

        texto = await self._extraer_texto(path)
        chunks = self._chunkear(texto)
        if not chunks:
            logger.warning("ingesta sin chunks: {}", path)
            return 0

        tipo = "image" if suffix in _IMAGE_SUFFIXES else suffix.lstrip(".")
        source_path = str(path.as_posix())
        return await self._embed_y_upsert(chunks=chunks, source_path=source_path, tipo=tipo)

    async def ingestar_carpeta(self, carpeta: Path) -> dict[str, int]:
        """Ingesta todos los archivos soportados de una carpeta."""
        if not carpeta.exists():
            return {}

        resultados: dict[str, int] = {}
        for path in sorted(carpeta.iterdir()):
            if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
                continue
            resultados[str(path)] = await self.ingestar_documento(path)
        return resultados

    async def _extraer_texto(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            pages = extraer_texto_pdf_por_paginas(path)
            total_pages = max(len(pages), 1)
            text_chars = sum(len(text) for text in pages)
            avg_chars_per_page = text_chars / total_pages
            logger.info(
                "pdf extraído con pypdf: archivo='{}' paginas={} chars={} promedio={:.2f}",
                path.name,
                total_pages,
                text_chars,
                avg_chars_per_page,
            )
            if avg_chars_per_page < _PDF_SCANNED_THRESHOLD:
                logger.warning(
                    "pdf detectado como escaneado/sin texto suficiente; fallback OpenAI Vision: archivo='{}' promedio={:.2f} (< {})",
                    path.name,
                    avg_chars_per_page,
                    _PDF_SCANNED_THRESHOLD,
                )
                return await self._ocr_pdf_with_openai(path)
            return extraer_texto_pdf(path)
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix in _IMAGE_SUFFIXES:
            mime = "image/png" if suffix == ".png" else "image/jpeg"
            return await self._openai.extract_text_from_image(path.read_bytes(), mime=mime)
        raise ValueError(f"Extensión no soportada: {suffix}")

    def _chunkear(self, texto: str) -> list[str]:
        return chunkear(
            texto=texto,
            max_chars=self._settings.chunk_max_chars,
            overlap=self._settings.chunk_overlap,
            max_chunks=self._settings.chunk_max,
        )

    async def _embed_y_upsert(self, chunks: list[str], source_path: str, tipo: str) -> int:
        vectors = await self._openai.embed_texts(chunks)
        now = datetime.now(timezone.utc).isoformat()
        source_name = Path(source_path).name

        points: list[qmodels.PointStruct] = []
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            point_id = str(uuid.uuid5(self._id_namespace, f"{source_path}|{idx}"))
            payload = {
                "texto": chunk,
                "source_path": source_path,
                "nombre_archivo": source_name,
                "tipo_fuente": tipo,
                "chunk_index": idx,
                "embedding_model": self._settings.openai_embedding_model,
                "embedding_dim": self._settings.embedding_dim,
                "schema_version": "1.0",
                "created_at": now,
            }
            points.append(qmodels.PointStruct(id=point_id, vector=vector, payload=payload))

        await self._qdrant.upsert_points(points)
        return len(points)

    async def _ocr_pdf_with_openai(self, path: Path) -> str:
        pdf = pdfium.PdfDocument(str(path))
        pages_text: list[str] = []
        try:
            for idx in range(len(pdf)):
                page = pdf[idx]
                bitmap = page.render(scale=2.0)
                png_bytes = self._bitmap_to_png_bytes(bitmap)
                extracted = await self._openai.extract_text_from_pdf_page(png_bytes)
                if extracted.strip():
                    pages_text.append(extracted.strip())
                logger.debug(
                    "pdf page OCR con OpenAI: archivo='{}' pagina={} chars_out={}",
                    path.name,
                    idx + 1,
                    len(extracted),
                )
        finally:
            pdf.close()
        return "\n\n".join(pages_text)

    @staticmethod
    def _bitmap_to_png_bytes(bitmap) -> bytes:  # noqa: ANN001
        width = int(bitmap.width)
        height = int(bitmap.height)
        stride = int(bitmap.stride)
        row_len = width * 3
        raw = memoryview(bitmap.buffer)

        # PNG scanlines: 1 byte de filtro (0) + datos RGB por fila.
        scanlines = bytearray()
        for y in range(height):
            start = y * stride
            end = start + row_len
            scanlines.append(0)
            scanlines.extend(raw[start:end])

        compressed = zlib.compress(bytes(scanlines), level=9)

        def chunk(chunk_type: bytes, data: bytes) -> bytes:
            crc = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
            return struct.pack("!I", len(data)) + chunk_type + data + struct.pack("!I", crc)

        png = bytearray(b"\x89PNG\r\n\x1a\n")
        png.extend(chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        png.extend(chunk(b"IDAT", compressed))
        png.extend(chunk(b"IEND", b""))
        return bytes(png)
