from __future__ import annotations

from loguru import logger
from openai import APIError, APITimeoutError, RateLimitError

from src.exceptions import (
    DocumentEmptyError,
    DocumentNotFoundError,
    OpenAIRateLimitError,
    OpenAIServiceError,
    QdrantUnavailableError,
)
from src.models import Fuente, QueryResponse
from src.services.document_retrieval import (
    ChunkRecord,
    DocumentRetrievalService,
    detect_intent,
)
from src.services.openai_service import OpenAIService
from src.services.qdrant_client import QdrantService
from src.settings import Settings
from src.utils.query_retrieval import build_retrieval_query

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

_SYSTEM_RAG_SUMMARY = (
    "Eres un asistente de aprendizaje. "
    "El usuario pide una explicación o resumen del documento indexado. "
    "Sintetiza la información del contexto de forma clara y estructurada. "
    "No inventes contenido que no esté en el contexto. "
    "Cita las fuentes como [Fuente N]. Responde en español."
)

_SYSTEM_RAG_FALLBACK = (
    "Eres un asistente de aprendizaje. "
    "No encontraste una coincidencia exacta en el documento para la pregunta, "
    "pero debes responder con base en los fragmentos disponibles del documento. "
    "Indica al inicio de forma breve que respondes con base en el contenido general "
    "del documento. No sugieras subir el archivo. "
    "Cita las fuentes como [Fuente N]. Responde en español."
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
        document_retrieval: DocumentRetrievalService | None = None,
    ) -> None:
        self._qdrant = qdrant_client
        self._openai = openai_service
        self._settings = settings
        self._doc_retrieval = document_retrieval or DocumentRetrievalService(qdrant_client)

    async def responder(
        self,
        pregunta: str,
        historial: list[dict[str, str]] | None = None,
        top_k: int = 5,
        umbral_score: float = 0.55,
        session_id: str | None = None,
        document_id: str | None = None,
        modo: str = "auto",
    ) -> QueryResponse:
        hist = historial or []
        intent = detect_intent(pregunta, modo)

        try:
            session_docs = await self._doc_retrieval.list_session_documents(session_id or "")
        except Exception as exc:  # noqa: BLE001
            logger.error("qdrant list_session_documents failed: {!r}", exc)
            raise QdrantUnavailableError() from exc

        if document_id and not any(d.document_id == document_id for d in session_docs):
            raise DocumentNotFoundError()

        target_document_id = self._doc_retrieval.resolve_document_id(
            pregunta, session_docs, document_id
        )
        target_doc = next((d for d in session_docs if d.document_id == target_document_id), None)

        if intent == "general" or (not target_document_id and not session_docs):
            return await self._responder_general(
                pregunta=pregunta,
                hist=hist,
                top_k=top_k,
                umbral_score=umbral_score,
                session_id=session_id,
            )

        if target_document_id and target_doc:
            return await self._responder_documento(
                pregunta=pregunta,
                hist=hist,
                top_k=top_k,
                umbral_score=umbral_score,
                session_id=session_id,
                document_id=target_document_id,
                nombre_archivo=target_doc.nombre_archivo,
                intent=intent,
            )

        if session_docs and intent != "general":
            mentioned = self._doc_retrieval.resolve_document_id(pregunta, session_docs, None)
            if mentioned:
                doc = next(d for d in session_docs if d.document_id == mentioned)
                return await self._responder_documento(
                    pregunta=pregunta,
                    hist=hist,
                    top_k=top_k,
                    umbral_score=umbral_score,
                    session_id=session_id,
                    document_id=doc.document_id,
                    nombre_archivo=doc.nombre_archivo,
                    intent=intent,
                )

        return await self._responder_general(
            pregunta=pregunta,
            hist=hist,
            top_k=top_k,
            umbral_score=umbral_score,
            session_id=session_id,
            has_session_docs=bool(session_docs),
        )

    async def _responder_documento(
        self,
        pregunta: str,
        hist: list[dict[str, str]],
        top_k: int,
        umbral_score: float,
        session_id: str | None,
        document_id: str,
        nombre_archivo: str,
        intent: str,
    ) -> QueryResponse:
        chunks: list[ChunkRecord] = []
        detalle = "Respuesta construida con recuperación documental (RAG)."
        system = _SYSTEM_RAG
        use_fallback = False

        if intent == "summary":
            chunks = await self._doc_retrieval.get_representative_chunks(
                session_id or "", document_id, nombre_archivo, n=top_k
            )
            system = _SYSTEM_RAG_SUMMARY
            detalle = "Resumen documental con chunks representativos."
        else:
            retrieval_query = build_retrieval_query(pregunta, hist)
            try:
                vector = await self._openai.embed_query(retrieval_query)
            except RateLimitError as exc:
                raise OpenAIRateLimitError() from exc
            except (APITimeoutError, APIError) as exc:
                raise OpenAIServiceError() from exc

            chunks = await self._doc_retrieval.search_document_chunks(
                vector=vector,
                session_id=session_id or "",
                document_id=document_id,
                nombre_archivo=nombre_archivo,
                limit=top_k,
            )
            above = [c for c in chunks if (c.score or 0.0) >= umbral_score]
            if above:
                chunks = above
                detalle = (
                    "Respuesta construida con recuperación semántica (RAG) filtrada por documento."
                )
            else:
                chunks = await self._doc_retrieval.get_representative_chunks(
                    session_id or "", document_id, nombre_archivo, n=top_k
                )
                system = _SYSTEM_RAG_FALLBACK
                use_fallback = True
                detalle = "Sin coincidencia exacta sobre umbral; respuesta con chunks del documento seleccionado."

        if not chunks:
            all_chunks = await self._doc_retrieval.get_document_chunks(
                session_id or "", document_id, nombre_archivo
            )
            if not all_chunks:
                raise DocumentEmptyError()
            chunks = all_chunks[:top_k]

        fuentes = [self._chunk_to_fuente(c) for c in chunks]
        contexto = "\n\n".join(
            f"[Fuente {idx + 1}] {fuente.excerpt}" for idx, fuente in enumerate(fuentes)
        )
        historial_texto = self._format_historial(hist)
        user_content = (
            f"{historial_texto}Contexto del documento '{nombre_archivo}':\n{contexto}\n\n"
            f"Pregunta actual:\n{pregunta}\n"
        )
        try:
            respuesta = await self._openai.generate(
                prompt=user_content,
                system=system,
                max_tokens=self._settings.openai_max_tokens_chat,
            )
        except RateLimitError as exc:
            raise OpenAIRateLimitError() from exc
        except (APITimeoutError, APIError) as exc:
            raise OpenAIServiceError() from exc

        if use_fallback and not respuesta.lower().startswith("no encontr"):
            respuesta = (
                "No encontré una coincidencia exacta, pero con base en el documento: " + respuesta
            )

        return QueryResponse(
            respuesta=respuesta,
            origen="rag",
            fuentes=fuentes,
            detalle_origen=detalle,
        )

    async def _responder_general(
        self,
        pregunta: str,
        hist: list[dict[str, str]],
        top_k: int,
        umbral_score: float,
        session_id: str | None,
        has_session_docs: bool = False,
    ) -> QueryResponse:
        retrieval_query = build_retrieval_query(pregunta, hist)
        try:
            vector = await self._openai.embed_query(retrieval_query)
        except RateLimitError as exc:
            raise OpenAIRateLimitError() from exc
        except (APITimeoutError, APIError) as exc:
            raise OpenAIServiceError() from exc

        try:
            hits = await self._qdrant.query(
                vector=vector,
                limit=top_k,
                session_id=session_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("qdrant query failed: {!r}", exc)
            raise QdrantUnavailableError() from exc

        fuentes_filtradas = [hit for hit in hits if (hit.score or 0.0) >= umbral_score]

        if fuentes_filtradas:
            fuentes = [self._hit_to_fuente(hit) for hit in fuentes_filtradas]
            contexto = "\n\n".join(
                f"[Fuente {idx + 1}] {fuente.excerpt}" for idx, fuente in enumerate(fuentes)
            )
            historial_texto = self._format_historial(hist)
            user_content = (
                f"{historial_texto}Contexto:\n{contexto}\n\nPregunta actual:\n{pregunta}\n"
            )
            try:
                respuesta = await self._openai.generate(
                    prompt=user_content,
                    system=_SYSTEM_RAG,
                    max_tokens=self._settings.openai_max_tokens_chat,
                )
            except RateLimitError as exc:
                raise OpenAIRateLimitError() from exc
            except (APITimeoutError, APIError) as exc:
                raise OpenAIServiceError() from exc
            return QueryResponse(
                respuesta=respuesta,
                origen="rag",
                fuentes=fuentes,
                detalle_origen="Respuesta construida con recuperación semántica (RAG).",
            )

        logger.info("query sin fuentes sobre umbral, usando modelo base")
        historial_texto = self._format_historial(hist)
        user_content = f"{historial_texto}Pregunta actual:\n{pregunta}\n"
        system = _SYSTEM_MODELO
        if has_session_docs:
            system = (
                "Eres un asistente de aprendizaje. Responde de forma precisa y breve en español. "
                "El usuario tiene documentos indexados en su sesión pero la pregunta no encaja "
                "con ninguno de forma clara. Responde con conocimiento general sin pedir subir archivos."
            )
        try:
            respuesta = await self._openai.generate(
                prompt=user_content,
                system=system,
                max_tokens=self._settings.openai_max_tokens_chat,
            )
        except RateLimitError as exc:
            raise OpenAIRateLimitError() from exc
        except (APITimeoutError, APIError) as exc:
            raise OpenAIServiceError() from exc
        return QueryResponse(
            respuesta=respuesta,
            origen="modelo",
            fuentes=[],
            detalle_origen="Sin contexto relevante en base vectorial; respuesta de modelo general.",
        )

    @staticmethod
    def _format_historial(hist: list[dict[str, str]]) -> str:
        if not hist:
            return ""
        lines: list[str] = ["Historial reciente:\n"]
        for msg in hist[-6:]:
            role = msg.get("role", "")
            content = (msg.get("content") or "").strip()
            if role == "agent" and len(content) > _MAX_AGENT_CONTENT_IN_PROMPT:
                content = content[:_MAX_AGENT_CONTENT_IN_PROMPT] + "…"
            label = "Usuario" if role == "user" else "Asistente"
            lines.append(f"{label}: {content}")
        lines.append("\n")
        return "\n".join(lines)

    @staticmethod
    def _chunk_to_fuente(chunk: ChunkRecord) -> Fuente:
        return Fuente(
            archivo=chunk.nombre_archivo,
            chunk_index=chunk.chunk_index,
            score=float(chunk.score or 1.0),
            excerpt=chunk.texto[:500],
        )

    @staticmethod
    def _hit_to_fuente(hit) -> Fuente:  # noqa: ANN001
        payload = hit.payload or {}
        return Fuente(
            archivo=str(payload.get("nombre_archivo") or "desconocido"),
            chunk_index=int(payload.get("chunk_index") or 0),
            score=float(hit.score or 0.0),
            excerpt=str(payload.get("texto") or "")[:500],
        )
