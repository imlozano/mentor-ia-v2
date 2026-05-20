from __future__ import annotations

from loguru import logger

from src.models import Fuente, QueryResponse
from src.services.openai_service import OpenAIService
from src.services.qdrant_client import QdrantService
from src.settings import Settings


class AgenteRespuesta:
    def __init__(
        self,
        qdrant_client: QdrantService,
        openai_service: OpenAIService,
        settings: Settings,
    ) -> None:
        self._qdrant = qdrant_client
        self._openai = openai_service
        self._settings = settings

    async def responder(
        self,
        pregunta: str,
        top_k: int = 5,
        umbral_score: float = 0.55,
        session_id: str | None = None,
    ) -> QueryResponse:
        vector = await self._openai.embed_query(pregunta)
        hits = await self._qdrant.query(vector=vector, limit=top_k, session_id=session_id)
        fuentes_filtradas = [hit for hit in hits if (hit.score or 0.0) >= umbral_score]

        if fuentes_filtradas:
            fuentes = [self._to_fuente(hit) for hit in fuentes_filtradas]
            contexto = "\n\n".join(
                f"[Fuente {idx + 1}] {fuente.excerpt}" for idx, fuente in enumerate(fuentes)
            )
            prompt = (
                "Responde de forma clara y útil en español, usando solo el contexto "
                "cuando sea pertinente. Cita referencias como [Fuente N] cuando uses "
                "información del contexto.\n\n"
                f"Contexto:\n{contexto}\n\n"
                f"Pregunta:\n{pregunta}\n"
            )
            respuesta = await self._openai.generate(
                prompt=prompt, max_tokens=self._settings.openai_max_tokens_chat
            )
            return QueryResponse(
                respuesta=respuesta,
                origen="rag",
                fuentes=fuentes,
                detalle_origen="Respuesta construida con recuperación semántica (RAG).",
            )

        logger.info("query sin fuentes sobre umbral, usando modelo base")
        respuesta = await self._openai.generate(
            prompt=f"Responde en español de forma precisa y breve:\n\n{pregunta}",
            max_tokens=self._settings.openai_max_tokens_chat,
        )
        return QueryResponse(
            respuesta=respuesta,
            origen="modelo",
            fuentes=[],
            detalle_origen="Sin contexto relevante en base vectorial; respuesta de modelo general.",
        )

    @staticmethod
    def _to_fuente(hit) -> Fuente:  # noqa: ANN001
        payload = hit.payload or {}
        return Fuente(
            archivo=str(payload.get("nombre_archivo") or "desconocido"),
            chunk_index=int(payload.get("chunk_index") or 0),
            score=float(hit.score or 0.0),
            excerpt=str(payload.get("texto") or "")[:500],
        )
