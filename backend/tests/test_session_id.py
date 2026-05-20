"""Tests de validación del session_id anónimo."""

from __future__ import annotations

import uuid

from src.utils.session_id import sanitize_session_id


def test_uuid4_valido_se_acepta():
    sid = str(uuid.uuid4())
    assert sanitize_session_id(sid) == sid


def test_uuid4_normaliza_mayusculas():
    sid = str(uuid.uuid4()).upper()
    out = sanitize_session_id(sid)
    assert out == sid.lower()


def test_none_devuelve_none():
    assert sanitize_session_id(None) is None


def test_cadena_vacia_devuelve_none():
    assert sanitize_session_id("") is None


def test_texto_arbitrario_devuelve_none():
    assert sanitize_session_id("../etc/passwd") is None
    assert sanitize_session_id("not-a-uuid") is None


def test_uuid_v1_se_rechaza():
    # Solo se acepta UUIDv4; un v1 no debe pasar.
    assert sanitize_session_id(str(uuid.uuid1())) is None


def test_valor_demasiado_largo_devuelve_none():
    assert sanitize_session_id("x" * 100) is None
