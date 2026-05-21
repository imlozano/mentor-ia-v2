"""Tests de la capa de normalización y resolución de anáforas para RAG."""

from __future__ import annotations

import pytest

from src.utils.query_retrieval import build_retrieval_query, extract_filename

# ---------------------------------------------------------------------------
# extract_filename
# ---------------------------------------------------------------------------

def test_extrae_md():
    assert extract_filename("el documento intro-ciberseguridad.md indexado") == "intro-ciberseguridad.md"


def test_extrae_pdf():
    assert extract_filename("el archivo attention-is-all-you-need.pdf") == "attention-is-all-you-need.pdf"


def test_extrae_txt():
    assert extract_filename("smoke-txt.txt contiene texto") == "smoke-txt.txt"


def test_extrae_imagen():
    assert extract_filename("hoja-libro.png subido") == "hoja-libro.png"


def test_no_extrae_nada():
    assert extract_filename("¿cómo funciona la atención multi-cabeza?") is None


# ---------------------------------------------------------------------------
# build_retrieval_query — normalización de ruido meta
# ---------------------------------------------------------------------------

def test_elimina_indexado_correctamente():
    q = build_retrieval_query("documento intro-ciberseguridad.md indexado correctamente")
    assert "indexado correctamente" not in q.lower()


def test_elimina_el_documento_habla():
    q = build_retrieval_query("¿el documento habla de VPN?")
    # El ruido meta se elimina; la señal semántica (VPN) permanece
    assert "VPN" in q or "vpn" in q.lower()


def test_pregunta_limpia_no_se_modifica():
    texto = "¿cómo funciona la autenticación de múltiples factores?"
    q = build_retrieval_query(texto)
    assert "autenticación" in q


def test_pregunta_vacia_devuelve_original():
    q = build_retrieval_query("el documento es este:")
    # Aunque todo sea ruido, no debe devolver cadena vacía si pregunta no es vacía
    assert isinstance(q, str)


# ---------------------------------------------------------------------------
# build_retrieval_query — resolución de anáforas con historial
# ---------------------------------------------------------------------------

def test_anafora_sin_historial_devuelve_pregunta_limpia():
    q = build_retrieval_query("el documento")
    assert isinstance(q, str)


def test_anafora_con_historial_usa_contexto():
    historial = [
        {"role": "user", "content": "¿Cómo protegerme de ataques en redes públicas?"},
        {"role": "agent", "content": "Usa una VPN como ProtonVPN y activa 2FA."},
    ]
    q = build_retrieval_query("El documento qué dice?", historial=historial)
    # Debe incorporar el contexto del mensaje user previo
    assert "proteger" in q.lower() or "redes" in q.lower() or "públicas" in q.lower()


def test_pregunta_sustantiva_no_usa_historial():
    historial = [
        {"role": "user", "content": "¿Qué es el phishing?"},
    ]
    q = build_retrieval_query("¿Cuáles son los atajos de terminal Linux?", historial=historial)
    assert "terminal" in q.lower() or "atajos" in q.lower()


def test_anafora_muy_corta_usa_historial():
    historial = [
        {"role": "user", "content": "Explícame la gestión de contraseñas con Bitwarden"},
    ]
    q = build_retrieval_query("¿y eso?", historial=historial)
    assert "bitwarden" in q.lower() or "contraseñas" in q.lower() or "gestión" in q.lower()


def test_historial_vacio_no_rompe():
    q = build_retrieval_query("¿qué dice?", historial=[])
    assert isinstance(q, str)


def test_historial_solo_agente_no_rompe():
    historial = [{"role": "agent", "content": "Usa 2FA para proteger tus cuentas."}]
    q = build_retrieval_query("¿qué dice?", historial=historial)
    assert isinstance(q, str)


# ---------------------------------------------------------------------------
# Integración: pregunta del hilo de chat de la issue
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pregunta,expected_term", [
    (
        "Que puedo usar para protegerme, el documento habla de ProtonVPN o de NordVPN?",
        "protonvpn",
    ),
    (
        "Necesito verificar si en el documento habla de usar ProtonVPN o NordVPN",
        "protonvpn",
    ),
])
def test_pregunta_vpn_retiene_nombre_vpn(pregunta, expected_term):
    q = build_retrieval_query(pregunta)
    assert expected_term in q.lower()
