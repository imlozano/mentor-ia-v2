"""Prompts y parser para planes de repaso espaciado (D+1, D+7, D+14, D+30).

La generación en una sola llamada evita que cada sesión repita las mismas
actividades genéricas (investigar + implementar + comparar en los cuatro días).
"""

from __future__ import annotations

import re

SESSION_ORDER: tuple[str, ...] = ("D+1", "D+7", "D+14", "D+30")

_BLOCK_HEADER_RE = re.compile(
    r"^\s*\[?(D\+1|D\+7|D\+14|D\+30)\]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_SYSTEM_PLAN = (
    "Eres un diseñador instruccional experto en repaso espaciado "
    "(curva del olvido de Ebbinghaus, intervalos D+1/D+7/D+14/D+30). "
    "Cada sesión tiene un rol pedagógico distinto; las actividades deben "
    "ser concretas, ejecutables en 30-60 minutos y NO repetirse entre sesiones. "
    "Responde únicamente en el formato solicitado, sin introducción ni cierre."
)

# Roles pedagógicos por sesión (usados en prompt único y en fallback por sesión).
SESSION_ROLES: dict[str, str] = {
    "D+1": (
        "Primera exposición (24 h después): reconocimiento y comprensión inicial. "
        "Prioriza definir conceptos clave, crear un mapa mental o esquema, y "
        "autoexplicar con tus palabras. Evita tareas largas de programación; "
        "solo pseudocódigo o ejemplos breves si aplica."
    ),
    "D+7": (
        "Primer refuerzo (7 días): práctica guiada y detección de lagunas. "
        "Incluye ejercicios aplicados, errores frecuentes del tema y comparar "
        "dos enfoques o variantes. No repitas mapas mentales ni definiciones "
        "literales de D+1."
    ),
    "D+14": (
        "Consolidación intermedia (14 días): integración y criterio. "
        "Propón un caso práctico o problema integrador, criterios para elegir "
        "entre alternativas y una conexión con un concepto adyacente del campo."
    ),
    "D+30": (
        "Retención a largo plazo (30 días): cierre y transferencia. "
        "Incluye autoevaluación sin apuntes, un mini-proyecto o simulacro "
        "de examen, y explicar el tema en 5 minutos como si enseñaras a otro."
    ),
}


def build_plan_prompt(tema: str, contexto: str) -> str:
    """Prompt único para generar las cuatro sesiones de una vez."""
    ctx_block = (
        contexto.strip()[:2000]
        if contexto.strip()
        else "(Sin material indexado; usa conocimiento estructurado del tema.)"
    )
    roles = "\n".join(f"- [{tipo}] {SESSION_ROLES[tipo]}" for tipo in SESSION_ORDER)
    return (
        f"Tema del plan: {tema}\n\n"
        f"Material de apoyo indexado (fragmentos relevantes):\n{ctx_block}\n\n"
        "Genera un plan de repaso espaciado con exactamente 4 bloques.\n"
        "Formato obligatorio (respeta etiquetas y orden):\n"
        "[D+1]\n"
        "<actividad 1 en una línea>\n"
        "<actividad 2 en una línea>\n"
        "<actividad 3 en una línea>\n"
        "[D+7]\n"
        "...\n"
        "[D+14]\n"
        "...\n"
        "[D+30]\n"
        "...\n\n"
        "Reglas:\n"
        "- Exactamente 3 actividades por bloque, una por línea, sin numeración ni viñetas.\n"
        "- Varía el tipo de tarea (escribir, practicar, explicar, diagramar, autoevaluar).\n"
        "- Si hay material indexado, ancla al menos una actividad por bloque a ese contenido.\n"
        "- Prohibido repetir la misma actividad o reformulación trivial entre bloques.\n\n"
        "Rol pedagógico de cada bloque:\n"
        f"{roles}\n"
    )


def build_session_fallback_prompt(
    tema: str,
    tipo: str,
    contexto: str,
    actividades_previas: list[str],
) -> str:
    """Prompt de una sola sesión cuando falla el parseo del plan completo."""
    previas = (
        "\n".join(f"- {a}" for a in actividades_previas) if actividades_previas else "(ninguna aún)"
    )
    ctx = contexto.strip()[:1200] if contexto.strip() else "(sin contexto indexado)"
    return (
        "Genera exactamente 3 actividades de estudio en español, una por línea, "
        "sin numeración ni viñetas.\n"
        f"Tema: {tema}\n"
        f"Sesión: {tipo}\n"
        f"Rol de esta sesión: {SESSION_ROLES[tipo]}\n\n"
        "Actividades ya asignadas en sesiones anteriores (NO repetir ni parafrasear):\n"
        f"{previas}\n\n"
        f"Contexto de apoyo:\n{ctx}\n"
    )


def _clean_activity_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[\d]+[\.\)]\s*", "", line)
    line = re.sub(r"^[-*•]\s*", "", line)
    return line.strip()


def parse_plan_response(raw: str) -> dict[str, list[str]]:
    """Parsea la salida del LLM en un dict tipo -> lista de 3 actividades."""
    text = raw.strip()
    if not text:
        return {}

    # Localizar inicios de bloque [D+1], etc.
    matches = list(_BLOCK_HEADER_RE.finditer(text))
    if not matches:
        return {}

    parsed: dict[str, list[str]] = {}
    for i, match in enumerate(matches):
        raw_tipo = match.group(1).upper()
        tipo = raw_tipo if raw_tipo in SESSION_ORDER else f"D+{raw_tipo.lstrip('D').lstrip('+')}"
        if tipo not in SESSION_ORDER:
            continue

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        lines = [_clean_activity_line(ln) for ln in body.splitlines() if ln.strip()]
        activities = [ln for ln in lines if len(ln) > 15][:3]
        if len(activities) >= 3:
            parsed[tipo] = activities

    return parsed


def merge_parsed_with_fallback(
    parsed: dict[str, list[str]],
    tema: str,
) -> dict[str, list[str]]:
    """Completa sesiones faltantes con placeholders diferenciados por tipo."""
    out = dict(parsed)
    for tipo in SESSION_ORDER:
        if tipo not in out or len(out[tipo]) < 3:
            out[tipo] = _generic_fallback(tema, tipo)
    return out


def _generic_fallback(tema: str, tipo: str) -> list[str]:
    """Fallback local diferenciado por sesión (sin OpenAI)."""
    templates: dict[str, list[str]] = {
        "D+1": [
            f"Elabora un mapa conceptual de {tema} con definiciones en tus propias palabras.",
            f"Lista los 5 conceptos nucleares de {tema} y un ejemplo concreto de cada uno.",
            f"Graba o escribe una explicación de 3 minutos de {tema} sin consultar apuntes.",
        ],
        "D+7": [
            f"Resuelve dos ejercicios aplicados de {tema} y corrige errores típicos del tema.",
            f"Compara dos variantes o enfoques dentro de {tema} en una tabla de pros y contras.",
            f"Identifica tres preguntas de examen sobre {tema} y responde una por escrito.",
        ],
        "D+14": [
            f"Diseña un caso práctico integrador de {tema} y documenta tu razonamiento paso a paso.",
            f"Establece criterios para elegir la mejor estrategia según el contexto en {tema}.",
            f"Relaciona {tema} con otro concepto del mismo campo y explica la conexión.",
        ],
        "D+30": [
            f"Autoevalúate sobre {tema} con 10 preguntas sin mirar material; repasa solo los fallos.",
            f"Completa un mini-proyecto o simulacro de examen de 45 minutos sobre {tema}.",
            f"Enseña {tema} a un compañero imaginario en 5 minutos y anota lagunas detectadas.",
        ],
    }
    return templates[tipo]
