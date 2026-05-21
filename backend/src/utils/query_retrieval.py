"""Utilidades para construir la consulta de recuperación semántica.

La consulta que se envía a embed_query no tiene que ser idéntica al texto
literal del usuario.  Dos transformaciones mejoran el recall del RAG:

1. Normalización: elimina frases meta-archivo que polutan el embedding
   hacia el chunk 0 / intro del documento en vez de su contenido.
2. Resolución de anáforas: si la pregunta actual es muy corta o anaforica
   ("el documento", "qué dice", "y eso") y hay historial, se prefija con
   el último mensaje `user` sustantivo para que el embedding busque sobre
   el tema real, no sobre la referencia deíctica.

Estas transformaciones solo afectan al vector de búsqueda; la pregunta
mostrada al usuario y enviada al LLM no se modifica.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Frases meta que no aportan señal semántica para recuperar chunks de contenido
# ---------------------------------------------------------------------------
_META_NOISE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bindexado\s+correctamente\b",
        r"\bindexado\b",
        r"\bel\s+documento\s+(dice|habla|menciona|tiene|contiene)?\b",
        r"\bel\s+archivo\s+(dice|habla|menciona|tiene|contiene)?\b",
        r"\bproporciona\s+(el\s+)?texto\b",
        r"\bpega\s+(el\s+)?(texto|contenido)\b",
        r"\bverificar\s+si\b",
        r"\bnecesito\s+verificar\b",
        r"\bel\s+documento\s+es\s+este\b",
        r"\bel\s+documento\s+al\s+que\s+te\s+refieres\b",
    ]
]

# Preguntas que son anafóricas o demasiado cortas para anclar un embedding útil
_ANAPHORIC_RE = re.compile(
    r"^(el\s+documento|qué\s+dice|qué\s+menciona|y\s+eso|esto|lo\s+anterior"
    r"|qué\s+hay\s+(ahí|allí)|puedes\s+ampliar|y\s+(esto|eso|aquello))[?.\s]*$",
    re.IGNORECASE,
)


def extract_filename(text: str) -> str | None:
    """Devuelve el primer nombre de archivo mencionado en el texto, o None."""
    match = re.search(r"[\w\-]+\.(md|pdf|txt|png|jpg|jpeg)\b", text, re.IGNORECASE)
    return match.group(0) if match else None


def _clean_meta_noise(text: str) -> str:
    """Elimina frases meta que no aportan señal semántica."""
    for pat in _META_NOISE_PATTERNS:
        text = pat.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _is_anaphoric(text: str) -> bool:
    """True si la pregunta es tan corta o deíctica que necesita contexto histórico."""
    cleaned = _clean_meta_noise(text)
    # Menos de 25 caracteres significativos o coincide con patron anafórico
    return len(cleaned) < 25 or bool(_ANAPHORIC_RE.match(cleaned))


def _last_user_message(historial: list[dict[str, str]]) -> str | None:
    """Devuelve el contenido del último mensaje de rol 'user' del historial."""
    for msg in reversed(historial):
        if msg.get("role") == "user":
            content = msg.get("content", "").strip()
            if len(content) > 10:
                return content
    return None


def build_retrieval_query(
    pregunta: str,
    historial: list[dict[str, str]] | None = None,
) -> str:
    """Construye la query de embedding para recuperación semántica.

    Args:
        pregunta: Pregunta literal del usuario (no se modifica externamente).
        historial: Lista de mensajes previos con claves ``role`` y ``content``.

    Returns:
        Texto optimizado para embed_query. Puede diferir de ``pregunta``
        cuando hay ruido meta o anáforas que se resuelven con el historial.
    """
    hist = historial or []

    cleaned = _clean_meta_noise(pregunta)

    # Si la pregunta es anafórica y hay historial, prefijar con último mensaje user
    if _is_anaphoric(cleaned) and hist:
        prior = _last_user_message(hist)
        if prior:
            prior_clean = _clean_meta_noise(prior)
            # Combinar: el contexto previo ancla el tema, la pregunta añade refinamiento
            combined = f"{prior_clean} {cleaned}".strip()
            return combined if combined else prior_clean

    return cleaned if cleaned else pregunta
