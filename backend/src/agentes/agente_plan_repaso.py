from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from loguru import logger

from src.agentes.agente_extraccion import AgenteExtraccion
from src.models import PlanRepasoResponse, SesionPlan
from src.services.make_webhook import MakeWebhookService
from src.services.openai_service import OpenAIService
from src.services.qdrant_client import QdrantService
from src.settings import Settings
from src.utils.plan_repaso_prompts import (
    _SYSTEM_PLAN,
    SESSION_ORDER,
    _clean_activity_line,
    _generic_fallback,
    build_plan_prompt,
    build_session_fallback_prompt,
    merge_parsed_with_fallback,
    parse_plan_response,
)

_SESSION_DELTAS: dict[str, int] = {"D+1": 1, "D+7": 7, "D+14": 14, "D+30": 30}


class AgentePlanRepaso:
    def __init__(
        self,
        qdrant_client: QdrantService,
        openai_service: OpenAIService,
        agente_extraccion: AgenteExtraccion,
        make_webhook: MakeWebhookService,
        settings: Settings,
    ) -> None:
        self._qdrant = qdrant_client
        self._openai = openai_service
        self._agente_extraccion = agente_extraccion
        self._make_webhook = make_webhook
        self._settings = settings

    async def generar_plan(
        self,
        tema: str,
        fecha_inicio: date,
        email: str | None = None,
        archivo: Path | None = None,
        session_id: str | None = None,
    ) -> PlanRepasoResponse:
        chunks_ingresados: int | None = None
        if archivo is not None:
            resultado = await self._agente_extraccion.ingestar_documento(archivo, session_id)
            chunks_ingresados = resultado.chunks_ingresados

        contexto = await self._buscar_contexto(tema, session_id)
        actividades_por_tipo = await self._generar_actividades(tema=tema, contexto=contexto)
        sesiones = self._armar_sesiones(
            tema=tema,
            fecha_inicio=fecha_inicio,
            actividades_por_tipo=actividades_por_tipo,
        )

        payload = {
            "tema": tema,
            "fecha_inicio": fecha_inicio.isoformat(),
            "sesiones": [s.model_dump(mode="json") for s in sesiones],
            "email": email,
        }
        email_enviado = False
        if email:
            email_enviado = await self._make_webhook.enviar_plan(payload)

        return PlanRepasoResponse(
            tema=tema,
            fecha_inicio=fecha_inicio,
            sesiones=sesiones,
            email_enviado=email_enviado,
            chunks_ingresados=chunks_ingresados,
        )

    async def _buscar_contexto(self, tema: str, session_id: str | None = None) -> str:
        query_vector = await self._openai.embed_query(tema)
        hits = await self._qdrant.query(vector=query_vector, limit=5, session_id=session_id)
        textos: list[str] = []
        for hit in hits:
            payload = hit.payload or {}
            texto = str(payload.get("texto") or "").strip()
            if texto:
                textos.append(texto[:500])
        return "\n\n".join(textos)

    async def _generar_actividades(self, tema: str, contexto: str) -> dict[str, list[str]]:
        """Genera las 12 actividades (3 × 4 sesiones) con progresión pedagógica."""
        try:
            raw = await self._openai.generate(
                prompt=build_plan_prompt(tema, contexto),
                system=_SYSTEM_PLAN,
                max_tokens=self._settings.openai_max_tokens_plan,
            )
            parsed = parse_plan_response(raw)
            if len(parsed) == 4:
                logger.debug("plan-repaso: plan completo parseado en una sola llamada")
                return parsed
            logger.warning(
                "plan-repaso: parseo incompleto ({} bloques), fallback por sesión",
                len(parsed),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "plan-repaso: error en generación unificada, fallback por sesión: {!r}",
                exc,
            )
            parsed = {}

        return await self._generar_actividades_por_sesion(
            tema=tema,
            contexto=contexto,
            parsed_partial=parsed,
        )

    async def _generar_actividades_por_sesion(
        self,
        tema: str,
        contexto: str,
        parsed_partial: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        """Completa o regenera sesiones con contexto de actividades ya asignadas."""
        resultado = dict(parsed_partial)
        acumuladas: list[str] = []
        for act_list in resultado.values():
            acumuladas.extend(act_list)

        for tipo in SESSION_ORDER:
            if tipo in resultado and len(resultado[tipo]) >= 3:
                continue
            descripcion = await self._generar_descripcion_sesion(
                tema=tema,
                tipo=tipo,
                contexto=contexto,
                actividades_previas=acumuladas,
            )
            resultado[tipo] = descripcion
            acumuladas.extend(descripcion)

        return merge_parsed_with_fallback(resultado, tema)

    async def _generar_descripcion_sesion(
        self,
        tema: str,
        tipo: str,
        contexto: str,
        actividades_previas: list[str],
    ) -> list[str]:
        prompt = build_session_fallback_prompt(
            tema=tema,
            tipo=tipo,
            contexto=contexto,
            actividades_previas=actividades_previas,
        )
        try:
            raw = await self._openai.generate(
                prompt=prompt,
                system=_SYSTEM_PLAN,
                max_tokens=min(500, self._settings.openai_max_tokens_plan),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "plan-repaso: fallback local en {}: {!r}",
                tipo,
                exc,
            )
            return _generic_fallback(tema, tipo)

        lines = [_clean_activity_line(ln) for ln in raw.splitlines() if ln.strip()]
        lines = [ln for ln in lines if len(ln) > 10]
        if len(lines) >= 3:
            return lines[:3]
        return _generic_fallback(tema, tipo)

    @staticmethod
    def _armar_sesiones(
        tema: str,
        fecha_inicio: date,
        actividades_por_tipo: dict[str, list[str]],
    ) -> list[SesionPlan]:
        sesiones: list[SesionPlan] = []
        for tipo in SESSION_ORDER:
            delta = _SESSION_DELTAS[tipo]
            sesiones.append(
                SesionPlan(
                    tipo=tipo,  # type: ignore[arg-type]
                    fecha=fecha_inicio + timedelta(days=delta),
                    titulo=f"Sesión {tipo} — {tema}",
                    descripcion=actividades_por_tipo.get(tipo, _generic_fallback(tema, tipo)),
                )
            )
        return sesiones
