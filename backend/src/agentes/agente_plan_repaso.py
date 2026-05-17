from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from loguru import logger

from src.agentes.agente_extraccion import AgenteExtraccion
from src.models import PlanRepasoResponse, SesionPlan
from src.services.make_webhook import MakeWebhookService
from src.services.openai_service import OpenAIService
from src.services.qdrant_client import QdrantService

_SESSION_DELTAS = [("D+1", 1), ("D+7", 7), ("D+14", 14), ("D+30", 30)]


class AgentePlanRepaso:
    def __init__(
        self,
        qdrant_client: QdrantService,
        openai_service: OpenAIService,
        agente_extraccion: AgenteExtraccion,
        make_webhook: MakeWebhookService,
    ) -> None:
        self._qdrant = qdrant_client
        self._openai = openai_service
        self._agente_extraccion = agente_extraccion
        self._make_webhook = make_webhook

    async def generar_plan(
        self,
        tema: str,
        fecha_inicio: date,
        email: str | None = None,
        archivo: Path | None = None,
    ) -> PlanRepasoResponse:
        chunks_ingresados: int | None = None
        if archivo is not None:
            chunks_ingresados = await self._agente_extraccion.ingestar_documento(archivo)

        contexto = await self._buscar_contexto(tema)
        sesiones = await self._generar_sesiones(tema=tema, fecha_inicio=fecha_inicio, contexto=contexto)

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

    async def _buscar_contexto(self, tema: str) -> str:
        query_vector = await self._openai.embed_query(tema)
        hits = await self._qdrant.query(vector=query_vector, limit=5)
        textos: list[str] = []
        for hit in hits:
            payload = hit.payload or {}
            texto = str(payload.get("texto") or "").strip()
            if texto:
                textos.append(texto[:500])
        return "\n\n".join(textos)

    async def _generar_sesiones(
        self,
        tema: str,
        fecha_inicio: date,
        contexto: str,
    ) -> list[SesionPlan]:
        sesiones: list[SesionPlan] = []
        for tipo, delta in _SESSION_DELTAS:
            fecha = fecha_inicio + timedelta(days=delta)
            descripcion = await self._generar_descripcion(
                tema=tema,
                tipo=tipo,
                contexto=contexto,
            )
            sesiones.append(
                SesionPlan(
                    tipo=tipo,
                    fecha=fecha,
                    titulo=f"Sesión {tipo} — {tema}",
                    descripcion=descripcion,
                )
            )
        return sesiones

    async def _generar_descripcion(self, tema: str, tipo: str, contexto: str) -> list[str]:
        prompt = (
            "Genera exactamente 3 actividades de estudio en español.\n"
            f"Tema: {tema}\n"
            f"Sesión: {tipo}\n"
            "Devuelve solo 3 líneas, una actividad por línea, sin numeración.\n"
            f"Contexto de apoyo (si existe):\n{contexto[:1500]}"
        )
        try:
            raw = await self._openai.generate(prompt=prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "plan-repaso: fallback local por error de generación OpenAI en {}: {!r}",
                tipo,
                exc,
            )
            return [
                f"Repasar conceptos clave de {tema} enfocados en {tipo}.",
                f"Resolver un ejercicio corto relacionado con {tema}.",
                f"Escribir un resumen de 5 ideas esenciales del tema.",
            ]
        lines = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()]
        if len(lines) >= 3:
            return lines[:3]
        return [
            f"Repasar conceptos clave de {tema} enfocados en {tipo}.",
            f"Resolver un ejercicio corto relacionado con {tema}.",
            f"Escribir un resumen de 5 ideas esenciales del tema.",
        ]

