from __future__ import annotations

import binascii
import struct
import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pypdfium2 as pdfium
from loguru import logger
from qdrant_client.http import models as qmodels

from src.services.openai_service import OpenAIService
from src.services.qdrant_client import QdrantService
from src.settings import Settings
from src.utils.chunking import chunkear, chunkear_markdown
from src.utils.document_id import compute_document_id, normalize_source_path
from src.utils.pdf_reader import extraer_texto_pdf, extraer_texto_pdf_por_paginas
from src.utils.upload_files import unlink_upload
from src.utils.upload_policy import IMAGE_EXTENSIONS, SUPPORTED_UPLOAD_EXTENSIONS

_SUPPORTED_SUFFIXES = SUPPORTED_UPLOAD_EXTENSIONS
_IMAGE_SUFFIXES = IMAGE_EXTENSIONS
_PDF_SCANNED_THRESHOLD = 50


@dataclass
class IngestaResult:
    """Resultado de ingestar un documento."""

    chunks_ingresados: int
    aviso: str | None = None
    document_id: str | None = None


def _cap_pdf_pages(total: int, limite: int) -> tuple[int, str | None]:
    """Decide cuántas páginas procesar y devuelve un aviso si hubo truncado.

    Función pura (sin pdfium) para poder testearla de forma aislada.
    """
    if limite > 0 and total > limite:
        aviso = (
            f"PDF truncado: se procesaron {limite} de {total} páginas "
            f"por el límite de OCR configurado."
        )
        return limite, aviso
    return total, None


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

    async def ingestar_documento(self, path: Path, session_id: str | None = None) -> IngestaResult:
        """Ingesta un documento y devuelve los chunks indexados y un aviso opcional."""
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Archivo no encontrado: {path}")

        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError(f"Extensión no soportada: {suffix}")

        texto, aviso = await self._extraer_texto(path)
        chunks = self._chunkear(texto, es_markdown=(suffix == ".md"))
        if not chunks:
            logger.warning("ingesta sin chunks: {}", path)
            return IngestaResult(chunks_ingresados=0, aviso=aviso)

        tipo = "image" if suffix in _IMAGE_SUFFIXES else suffix.lstrip(".")
        source_path = normalize_source_path(str(path.as_posix()))
        source_name = path.name
        document_id = compute_document_id(session_id or "", source_name) if session_id else None
        chunks_ingresados = await self._embed_y_upsert(
            chunks=chunks,
            source_path=source_path,
            tipo=tipo,
            session_id=session_id,
            document_id=document_id,
            nombre_archivo=source_name,
        )
        return IngestaResult(
            chunks_ingresados=chunks_ingresados,
            aviso=aviso,
            document_id=document_id,
        )

    async def ingestar_carpeta(
        self, carpeta: Path, session_id: str | None = None
    ) -> dict[str, IngestaResult]:
        """Ingesta todos los archivos soportados de una carpeta."""
        if not carpeta.exists():
            return {}

        resultados: dict[str, IngestaResult] = {}
        for path in sorted(carpeta.iterdir()):
            if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
                continue
            resultados[str(path)] = await self.ingestar_documento(path, session_id)
        return resultados

    async def _extraer_texto(self, path: Path) -> tuple[str, str | None]:
        """Devuelve (texto, aviso). El aviso solo se rellena si hubo truncado OCR."""
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
            return extraer_texto_pdf(path), None
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore"), None
        if suffix in _IMAGE_SUFFIXES:
            mime = "image/png" if suffix == ".png" else "image/jpeg"
            texto = await self._openai.extract_text_from_image(
                path.read_bytes(),
                mime=mime,
                max_tokens=self._settings.openai_max_tokens_ocr,
            )
            return texto, None
        raise ValueError(f"Extensión no soportada: {suffix}")

    def _chunkear(self, texto: str, es_markdown: bool = False) -> list[str]:
        fn = chunkear_markdown if es_markdown else chunkear
        return fn(
            texto=texto,
            max_chars=self._settings.chunk_max_chars,
            overlap=self._settings.chunk_overlap,
            max_chunks=self._settings.chunk_max,
        )

    async def _embed_y_upsert(
        self,
        chunks: list[str],
        source_path: str,
        tipo: str,
        session_id: str | None = None,
        document_id: str | None = None,
        nombre_archivo: str | None = None,
    ) -> int:
        source_name = nombre_archivo or Path(source_path).name
        if session_id and document_id:
            await self._qdrant.delete_by_document(session_id, document_id, source_name)

        vectors = await self._openai.embed_texts(chunks)
        now = datetime.now(timezone.utc).isoformat()

        points: list[qmodels.PointStruct] = []
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            point_id = str(
                uuid.uuid5(self._id_namespace, f"{session_id or ''}|{source_path}|{idx}")
            )
            payload = {
                "texto": chunk,
                "source_path": source_path,
                "nombre_archivo": source_name,
                "document_id": document_id,
                "tipo_fuente": tipo,
                "chunk_index": idx,
                "session_id": session_id,
                "embedding_model": self._settings.openai_embedding_model,
                "embedding_dim": self._settings.embedding_dim,
                "schema_version": "1.2",
                "created_at": now,
            }
            points.append(qmodels.PointStruct(id=point_id, vector=vector, payload=payload))

        await self._qdrant.upsert_points(points)
        ingested = len(points)
        if session_id and ingested > 0:
            unlink_upload(self._settings, source_name)
        return ingested

    async def _ocr_pdf_with_openai(self, path: Path) -> tuple[str, str | None]:
        pdf = pdfium.PdfDocument(str(path))
        pages_text: list[str] = []
        try:
            total_pages = len(pdf)
            paginas_a_procesar, aviso = _cap_pdf_pages(
                total_pages, self._settings.ocr_pdf_max_pages
            )
            if aviso:
                logger.warning(
                    "ocr-pdf: {} (archivo='{}')",
                    aviso,
                    path.name,
                )
            for idx in range(paginas_a_procesar):
                page = pdf[idx]
                bitmap = page.render(scale=2.0)
                png_bytes = self._bitmap_to_png_bytes(bitmap)
                extracted = await self._openai.extract_text_from_pdf_page(
                    png_bytes, max_tokens=self._settings.openai_max_tokens_ocr
                )
                if extracted.strip():
                    pages_text.append(extracted.strip())
                logger.debug(
                    "pdf page OCR con OpenAI: archivo='{}' pagina={}/{} chars_out={}",
                    path.name,
                    idx + 1,
                    paginas_a_procesar,
                    len(extracted),
                )
        finally:
            pdf.close()
        return "\n\n".join(pages_text), aviso

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
