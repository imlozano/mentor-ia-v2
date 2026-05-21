from __future__ import annotations

from loguru import logger

from src.models import Fuente, QueryResponse
from src.services.openai_service import OpenAIService
from src.services.qdrant_client import QdrantService
from src.settings import Settings
from src.utils.query_retrieval import build_retrieval_query, extract_filename

# Máximo de chars del contenido de un mensaje de agente incluido en el historial
# del prompt (evita inflar tokens con respuestas largas previas).
_MAX_AGENT_CONTENT_IN_PROMPT = 500

_SYSTEM_RAG = (
    "Eres un asistente de aprendizaje. "
    "Responde ÚNICAMENTE con la información del contexto proporcionado. "
    "Si el usuario pregunta si un documento menciona algo específico, "
    "di explícitamente qué sí aparece en el contexto y qué NO aparece. "
    "No añadas información de conocimiento general que no esté en el contexto. "
    "Si el contexto no contiene suficiente información para responder, di: "
    "'No consta en los documentos indexados.' "
    "Cita las fuentes como [Fuente N] cuando uses información del contexto. "
    "Responde en español."
)

_SYSTEM_MODELO = (
    "Eres un asistente de aprendizaje. "
    "Responde de forma precisa y breve en español. "
    "Si la pregunta parece referirse a un documento concreto que el usuario subió, "
    "indica que no hay documentos indexados relevantes y sugiere subir el archivo."
)


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
        historial: list[dict[str, str]] | None = None,
        top_k: int = 5,
        umbral_score: float = 0.55,
        session_id: str | None = None,
    ) -> QueryResponse:
        hist = historial or []

        # Construir la query de embedding (puede diferir del texto literal si hay
        # anáforas o ruido meta — ver query_retrieval.py para la lógica completa).
        retrieval_query = build_retrieval_query(pregunta, hist)
        nombre_archivo = extract_filename(pregunta)

        logger.debug(
            "query retrieval: original={!r} → embedding={!r} archivo={!r}",
            pregunta,
            retrieval_query,
            nombre_archivo,
        )

        vector = await self._openai.embed_query(retrieval_query)
        hits = await self._qdrant.query(
            vector=vector,
            limit=top_k,
            session_id=session_id,
            nombre_archivo=nombre_archivo,
        )
        fuentes_filtradas = [hit for hit in hits if (hit.score or 0.0) >= umbral_score]

        if fuentes_filtradas:
            fuentes = [self._to_fuente(hit) for hit in fuentes_filtradas]
            contexto = "\n\n".join(
                f"[Fuente {idx + 1}] {fuente.excerpt}" for idx, fuente in enumerate(fuentes)
            )
            historial_texto = self._format_historial(hist)
            user_content = (
                f"{historial_texto}Contexto:\n{contexto}\n\nPregunta actual:\n{pregunta}\n"
            )
            respuesta = await self._openai.generate(
                prompt=user_content,
                system=_SYSTEM_RAG,
                max_tokens=self._settings.openai_max_tokens_chat,
            )
            return QueryResponse(
                respuesta=respuesta,
                origen="rag",
                fuentes=fuentes,
                detalle_origen="Respuesta construida con recuperación semántica (RAG).",
            )

        logger.info("query sin fuentes sobre umbral, usando modelo base")
        historial_texto = self._format_historial(hist)
        user_content = f"{historial_texto}Pregunta actual:\n{pregunta}\n"
        respuesta = await self._openai.generate(
            prompt=user_content,
            system=_SYSTEM_MODELO,
            max_tokens=self._settings.openai_max_tokens_chat,
        )
        return QueryResponse(
            respuesta=respuesta,
            origen="modelo",
            fuentes=[],
            detalle_origen="Sin contexto relevante en base vectorial; respuesta de modelo general.",
        )

    @staticmethod
    def _format_historial(hist: list[dict[str, str]]) -> str:
        """Formatea los últimos mensajes del historial para incluir en el prompt."""
        if not hist:
            return ""
        lines: list[str] = ["Historial reciente:\n"]
        for msg in hist[-6:]:
            role = msg.get("role", "")
            content = (msg.get("content") or "").strip()
            # Truncar mensajes largos del agente para no inflar tokens
            if role == "agent" and len(content) > _MAX_AGENT_CONTENT_IN_PROMPT:
                content = content[:_MAX_AGENT_CONTENT_IN_PROMPT] + "…"
            label = "Usuario" if role == "user" else "Asistente"
            lines.append(f"{label}: {content}")
        lines.append("\n")
        return "\n".join(lines)

    @staticmethod
    def _to_fuente(hit) -> Fuente:  # noqa: ANN001
        payload = hit.payload or {}
        return Fuente(
            archivo=str(payload.get("nombre_archivo") or "desconocido"),
            chunk_index=int(payload.get("chunk_index") or 0),
            score=float(hit.score or 0.0),
            excerpt=str(payload.get("texto") or "")[:500],
        )
