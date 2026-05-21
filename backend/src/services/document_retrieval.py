"""Recuperación de chunks por documento e intención de consulta."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.services.qdrant_client import QdrantService
from src.utils.document_id import derive_document_id
from src.utils.query_retrieval import extract_filename

_SUMMARY_RE = re.compile(
    r"\b("
    r"expl[ií]came|resume|resumen|sumario|overview|"
    r"qu[eé]\s+dice|de\s+qu[eé]\s+trata|"
    r"este\s+documento|el\s+documento|"
    r"habla\s+de|trata\s+sobre"
    r")\b",
    re.IGNORECASE,
)

_ANAPHORIC_DOC_RE = re.compile(
    r"\b(este\s+documento|el\s+documento|este\s+archivo|el\s+archivo)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SessionDocument:
    document_id: str
    nombre_archivo: str
    tipo_fuente: str
    total_chunks: int


@dataclass(frozen=True)
class ChunkRecord:
    texto: str
    chunk_index: int
    nombre_archivo: str
    document_id: str
    score: float | None = None


def normalize_doc_name(name: str) -> str:
    stem = Path(name).stem.lower().replace("_", "-").replace(" ", "-")
    return re.sub(r"-+", "-", stem)


def detect_intent(pregunta: str, modo: str) -> str:
    if modo == "general":
        return "general"
    if modo == "documento":
        return "summary"
    if _SUMMARY_RE.search(pregunta) or _ANAPHORIC_DOC_RE.search(pregunta):
        return "summary"
    return "specific"


def pick_representative_indices(total: int, n: int = 5) -> list[int]:
    if total <= 0:
        return []
    if total <= n:
        return list(range(total))
    indices = {0, total - 1}
    step = (total - 1) / (n - 1)
    for i in range(n):
        indices.add(min(total - 1, round(i * step)))
    return sorted(indices)


class DocumentRetrievalService:
    def __init__(self, qdrant: QdrantService) -> None:
        self._qdrant = qdrant

    async def list_session_documents(self, session_id: str) -> list[SessionDocument]:
        grouped: dict[str, SessionDocument] = {}
        async for record in self._qdrant.scroll_all(session_id=session_id):
            payload = record.payload or {}
            doc_id = derive_document_id(payload, session_id)
            if not doc_id:
                continue
            nombre = str(
                payload.get("nombre_archivo") or Path(str(payload.get("source_path") or "")).name
            )
            tipo = str(payload.get("tipo_fuente") or "txt")
            if doc_id in grouped:
                existing = grouped[doc_id]
                grouped[doc_id] = SessionDocument(
                    document_id=doc_id,
                    nombre_archivo=existing.nombre_archivo,
                    tipo_fuente=existing.tipo_fuente,
                    total_chunks=existing.total_chunks + 1,
                )
            else:
                grouped[doc_id] = SessionDocument(
                    document_id=doc_id,
                    nombre_archivo=nombre,
                    tipo_fuente=tipo,
                    total_chunks=1,
                )
        return sorted(grouped.values(), key=lambda d: d.nombre_archivo.lower())

    def resolve_document_id(
        self,
        pregunta: str,
        docs: list[SessionDocument],
        explicit_document_id: str | None = None,
    ) -> str | None:
        if explicit_document_id:
            if any(d.document_id == explicit_document_id for d in docs):
                return explicit_document_id
            return None

        filename = extract_filename(pregunta)
        if filename:
            for doc in docs:
                if doc.nombre_archivo.lower() == filename.lower():
                    return doc.document_id

        pregunta_norm = normalize_doc_name(pregunta)
        for doc in docs:
            doc_norm = normalize_doc_name(doc.nombre_archivo)
            if doc_norm and (doc_norm in pregunta_norm or pregunta_norm in doc_norm):
                return doc.document_id
            tokens = [t for t in re.split(r"[\s\-_]+", pregunta_norm) if len(t) > 2]
            doc_tokens = set(re.split(r"[\s\-_]+", doc_norm))
            if len(tokens) >= 2 and sum(1 for t in tokens if t in doc_tokens) >= len(tokens) // 2 + 1:
                return doc.document_id
        return None

    async def get_document_chunks(
        self,
        session_id: str,
        document_id: str,
        nombre_archivo: str | None = None,
    ) -> list[ChunkRecord]:
        chunks: list[ChunkRecord] = []
        async for record in self._qdrant.scroll_by_document(
            session_id=session_id,
            document_id=document_id,
            nombre_archivo=nombre_archivo,
        ):
            payload = record.payload or {}
            chunks.append(
                ChunkRecord(
                    texto=str(payload.get("texto") or ""),
                    chunk_index=int(payload.get("chunk_index") or 0),
                    nombre_archivo=str(payload.get("nombre_archivo") or nombre_archivo or ""),
                    document_id=document_id,
                )
            )
        chunks.sort(key=lambda c: c.chunk_index)
        return chunks

    async def get_representative_chunks(
        self,
        session_id: str,
        document_id: str,
        nombre_archivo: str | None = None,
        n: int = 5,
    ) -> list[ChunkRecord]:
        all_chunks = await self.get_document_chunks(session_id, document_id, nombre_archivo)
        if not all_chunks:
            return []
        indices = pick_representative_indices(len(all_chunks), n)
        return [
            ChunkRecord(
                texto=all_chunks[i].texto,
                chunk_index=all_chunks[i].chunk_index,
                nombre_archivo=all_chunks[i].nombre_archivo,
                document_id=document_id,
                score=1.0,
            )
            for i in indices
        ]

    async def search_document_chunks(
        self,
        vector: list[float],
        session_id: str,
        document_id: str,
        nombre_archivo: str | None,
        limit: int,
    ) -> list[ChunkRecord]:
        hits = await self._qdrant.query(
            vector=vector,
            limit=limit,
            session_id=session_id,
            document_id=document_id,
            nombre_archivo=nombre_archivo,
            strict_document_filter=True,
        )
        records: list[ChunkRecord] = []
        for hit in hits:
            payload = hit.payload or {}
            records.append(
                ChunkRecord(
                    texto=str(payload.get("texto") or ""),
                    chunk_index=int(payload.get("chunk_index") or 0),
                    nombre_archivo=str(payload.get("nombre_archivo") or nombre_archivo or ""),
                    document_id=document_id,
                    score=float(hit.score or 0.0),
                )
            )
        return records
