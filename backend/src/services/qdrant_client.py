"""Wrapper sobre qdrant-client para Mentor IA."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from src.settings import Settings


class QdrantService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            prefer_grpc=False,
            timeout=10.0,
        )

    @property
    def collection(self) -> str:
        return self._settings.qdrant_collection

    async def ensure_collection(self) -> None:
        existing = await self._client.get_collections()
        names = {c.name for c in existing.collections}
        if self.collection in names:
            logger.debug("qdrant: colección '{}' ya existe", self.collection)
        else:
            await self._client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(
                    size=self._settings.embedding_dim,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            logger.info(
                "qdrant: colección '{}' creada ({}d, COSINE)",
                self.collection,
                self._settings.embedding_dim,
            )

        await self._ensure_payload_index("session_id")
        await self._ensure_payload_index("document_id")
        await self._ensure_payload_index("nombre_archivo")

    async def _ensure_payload_index(self, field_name: str) -> None:
        try:
            await self._client.create_payload_index(
                collection_name=self.collection,
                field_name=field_name,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("qdrant: no se pudo crear índice {}: {!r}", field_name, exc)

    @staticmethod
    def _session_filter(session_id: str | None) -> qmodels.Filter | None:
        if not session_id:
            return None
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="session_id",
                    match=qmodels.MatchValue(value=session_id),
                )
            ]
        )

    @staticmethod
    def _document_scope_filter(
        session_id: str | None,
        document_id: str | None = None,
        nombre_archivo: str | None = None,
    ) -> qmodels.Filter | None:
        must: list[qmodels.FieldCondition] = []
        if session_id:
            must.append(
                qmodels.FieldCondition(
                    key="session_id",
                    match=qmodels.MatchValue(value=session_id),
                )
            )
        should: list[qmodels.FieldCondition] = []
        if document_id:
            should.append(
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=document_id),
                )
            )
        if nombre_archivo:
            should.append(
                qmodels.FieldCondition(
                    key="nombre_archivo",
                    match=qmodels.MatchValue(value=nombre_archivo),
                )
            )
        if not must and not should:
            return None
        if should:
            return qmodels.Filter(
                must=must or None,
                min_should=qmodels.MinShould(conditions=should, min_count=1),
            )
        return qmodels.Filter(must=must)

    @staticmethod
    def _combined_filter(
        session_id: str | None,
        nombre_archivo: str | None = None,
        document_id: str | None = None,
    ) -> qmodels.Filter | None:
        if document_id:
            return QdrantService._document_scope_filter(session_id, document_id, nombre_archivo)
        conditions: list[qmodels.FieldCondition] = []
        if session_id:
            conditions.append(
                qmodels.FieldCondition(
                    key="session_id",
                    match=qmodels.MatchValue(value=session_id),
                )
            )
        if nombre_archivo:
            conditions.append(
                qmodels.FieldCondition(
                    key="nombre_archivo",
                    match=qmodels.MatchValue(value=nombre_archivo),
                )
            )
        if not conditions:
            return None
        return qmodels.Filter(must=conditions)

    async def ping(self, timeout: float = 2.0) -> bool:
        try:
            await asyncio.wait_for(self._client.get_collections(), timeout=timeout)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("qdrant ping failed: {!r}", exc)
            return False

    async def upsert_points(self, points: list[qmodels.PointStruct]) -> None:
        if not points:
            return
        await self._client.upsert(collection_name=self.collection, points=points)

    async def delete_by_document(
        self,
        session_id: str,
        document_id: str,
        nombre_archivo: str | None = None,
    ) -> None:
        """Elimina chunks del documento (por document_id y legacy por nombre)."""
        must = [
            qmodels.FieldCondition(
                key="session_id",
                match=qmodels.MatchValue(value=session_id),
            ),
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchValue(value=document_id),
            ),
        ]
        await self._client.delete(
            collection_name=self.collection,
            points_selector=qmodels.FilterSelector(filter=qmodels.Filter(must=must)),
        )
        if nombre_archivo:
            legacy_must = [
                qmodels.FieldCondition(
                    key="session_id",
                    match=qmodels.MatchValue(value=session_id),
                ),
                qmodels.FieldCondition(
                    key="nombre_archivo",
                    match=qmodels.MatchValue(value=nombre_archivo),
                ),
            ]
            try:
                await self._client.delete(
                    collection_name=self.collection,
                    points_selector=qmodels.FilterSelector(filter=qmodels.Filter(must=legacy_must)),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("qdrant: delete legacy por nombre_archivo falló: {!r}", exc)

    async def query(
        self,
        vector: list[float],
        limit: int,
        score_threshold: float | None = None,
        session_id: str | None = None,
        nombre_archivo: str | None = None,
        document_id: str | None = None,
        strict_document_filter: bool = False,
    ) -> list[qmodels.ScoredPoint]:
        query_filter = self._combined_filter(session_id, nombre_archivo, document_id)
        result = await self._client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
            with_payload=True,
        )
        if not result.points and nombre_archivo and not strict_document_filter:
            fallback_filter = self._session_filter(session_id)
            result = await self._client.query_points(
                collection_name=self.collection,
                query=vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=fallback_filter,
                with_payload=True,
            )
        return result.points

    async def scroll_all(
        self, batch: int = 256, session_id: str | None = None
    ) -> AsyncIterator[qmodels.Record]:
        offset: Any = None
        scroll_filter = self._session_filter(session_id)
        while True:
            records, offset = await self._client.scroll(
                collection_name=self.collection,
                scroll_filter=scroll_filter,
                limit=batch,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for r in records:
                yield r
            if offset is None:
                return

    async def scroll_by_document(
        self,
        session_id: str,
        document_id: str,
        nombre_archivo: str | None = None,
        batch: int = 256,
    ) -> AsyncIterator[qmodels.Record]:
        offset: Any = None
        scroll_filter = self._document_scope_filter(session_id, document_id, nombre_archivo)
        while True:
            records, offset = await self._client.scroll(
                collection_name=self.collection,
                scroll_filter=scroll_filter,
                limit=batch,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for r in records:
                yield r
            if offset is None:
                return

    async def close(self) -> None:
        await self._client.close()
