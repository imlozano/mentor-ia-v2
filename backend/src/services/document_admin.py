"""Operaciones administrativas de documentos (borrado por sesión)."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.document_retrieval import DocumentRetrievalService
from src.services.qdrant_client import QdrantService
from src.settings import Settings
from src.utils.upload_files import unlink_upload


@dataclass(frozen=True)
class DeleteOneResult:
    document_id: str
    nombre_archivo: str
    chunks_eliminados: int
    archivo_local_eliminado: bool


@dataclass(frozen=True)
class VaciarSesionResult:
    documentos_eliminados: int
    chunks_eliminados: int
    archivos_locales_eliminados: int


class DocumentAdminService:
    def __init__(
        self,
        qdrant: QdrantService,
        retrieval: DocumentRetrievalService,
        settings: Settings,
    ) -> None:
        self._qdrant = qdrant
        self._retrieval = retrieval
        self._settings = settings

    async def delete_one(self, session_id: str, document_id: str) -> DeleteOneResult | None:
        """Borra un documento de la sesión. None si no existe en esa sesión."""
        chunks = await self._retrieval.get_document_chunks(
            session_id=session_id,
            document_id=document_id,
        )
        if not chunks:
            return None

        nombre_archivo = chunks[0].nombre_archivo
        chunks_count = len(chunks)

        await self._qdrant.delete_by_document(
            session_id=session_id,
            document_id=document_id,
            nombre_archivo=nombre_archivo,
        )

        archivo_local_eliminado = unlink_upload(self._settings, nombre_archivo)

        return DeleteOneResult(
            document_id=document_id,
            nombre_archivo=nombre_archivo,
            chunks_eliminados=chunks_count,
            archivo_local_eliminado=archivo_local_eliminado,
        )

    async def vaciar_sesion(self, session_id: str) -> VaciarSesionResult:
        """Elimina todos los chunks de la sesión y archivos locales referenciados."""
        docs = await self._retrieval.list_session_documents(session_id)
        chunks_eliminados = sum(d.total_chunks for d in docs)
        documentos_eliminados = len(docs)

        await self._qdrant.delete_by_session(session_id)

        archivos_locales_eliminados = 0
        nombres_vistos: set[str] = set()
        for doc in docs:
            if doc.nombre_archivo in nombres_vistos:
                continue
            nombres_vistos.add(doc.nombre_archivo)
            if unlink_upload(self._settings, doc.nombre_archivo):
                archivos_locales_eliminados += 1

        return VaciarSesionResult(
            documentos_eliminados=documentos_eliminados,
            chunks_eliminados=chunks_eliminados,
            archivos_locales_eliminados=archivos_locales_eliminados,
        )
