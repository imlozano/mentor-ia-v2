"""Wrapper sobre qdrant-client para Mentor IA.

Encapsula la conexión al cluster Qdrant Cloud y expone solo lo que el resto
del backend necesita: crear la colección si no existe, hacer ping, upsert,
query y scroll.
"""

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
        """Crea la colección si no existe. Idempotente."""
        existing = await self._client.get_collections()
        names = {c.name for c in existing.collections}
        if self.collection in names:
            logger.debug("qdrant: colección '{}' ya existe", self.collection)
            return

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

    async def ping(self, timeout: float = 2.0) -> bool:
        """Verifica conectividad con get_collections. Devuelve True/False."""
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

    async def query(
        self,
        vector: list[float],
        limit: int,
        score_threshold: float | None = None,
    ) -> list[qmodels.ScoredPoint]:
        result = await self._client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return result.points

    async def scroll_all(self, batch: int = 256) -> AsyncIterator[qmodels.Record]:
        """Itera sobre todos los puntos de la colección."""
        offset: Any = None
        while True:
            records, offset = await self._client.scroll(
                collection_name=self.collection,
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
