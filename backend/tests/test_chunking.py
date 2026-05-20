"""Tests del troceado de texto."""

from __future__ import annotations

import pytest

from src.utils.chunking import chunkear


def test_texto_vacio_devuelve_lista_vacia():
    assert chunkear("") == []
    assert chunkear("   ") == []


def test_texto_corto_un_solo_chunk():
    out = chunkear("hola mundo", max_chars=900, overlap=150)
    assert out == ["hola mundo"]


def test_respeta_max_chars():
    texto = "x" * 5000
    out = chunkear(texto, max_chars=900, overlap=150)
    assert all(len(c) <= 900 for c in out)


def test_respeta_max_chunks():
    texto = "palabra " * 5000
    out = chunkear(texto, max_chars=100, overlap=10, max_chunks=5)
    assert len(out) == 5


def test_hay_solape_entre_chunks():
    texto = "abcdefghij" * 200  # 2000 chars
    out = chunkear(texto, max_chars=500, overlap=100)
    assert len(out) >= 2
    # El final del chunk 0 debe reaparecer al inicio del chunk 1.
    assert out[0][-100:] == out[1][:100]


def test_parametros_invalidos_lanzan_error():
    with pytest.raises(ValueError):
        chunkear("texto", max_chars=0)
    with pytest.raises(ValueError):
        chunkear("texto", max_chars=100, overlap=100)
    with pytest.raises(ValueError):
        chunkear("texto", max_chars=100, overlap=10, max_chunks=0)
