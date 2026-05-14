from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from loguru import logger
from qdrant_client.http import models as qmodels

from src.services.gemini import GeminiService
from src.services.qdrant_client import QdrantService
from src.services.vision import VisionService
from src.settings import Settings
from src.utils.chunking import chunkear
from src.utils.pdf_reader import extraer_texto_pdf

_SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


class AgenteExtraccion:
    def __init__(
        self,
        qdrant_client: QdrantService,
        gemini_service: GeminiService,
        vision_service: VisionService,
        settings: Settings,
    ) -> None:
        self._qdrant = qdrant_client
        self._gemini = gemini_service
        self._vision = vision_service
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
            return extraer_texto_pdf(path)
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix in _IMAGE_SUFFIXES:
            mime = "image/png" if suffix == ".png" else "image/jpeg"
            return await self._vision.ocr(path.read_bytes(), mime=mime)
        raise ValueError(f"Extensión no soportada: {suffix}")

    def _chunkear(self, texto: str) -> list[str]:
        return chunkear(
            texto=texto,
            max_chars=self._settings.chunk_max_chars,
            overlap=self._settings.chunk_overlap,
            max_chunks=self._settings.chunk_max,
        )

    async def _embed_y_upsert(self, chunks: list[str], source_path: str, tipo: str) -> int:
        vectors = await self._gemini.embed_texts(chunks)
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
                "embedding_model": self._settings.embedding_model,
                "embedding_dim": self._settings.embedding_dim,
                "schema_version": "1.0",
                "created_at": now,
            }
            points.append(qmodels.PointStruct(id=point_id, vector=vector, payload=payload))

        await self._qdrant.upsert_points(points)
        return len(points)

