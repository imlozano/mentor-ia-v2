"""Tests de chunkear_markdown: respeta encabezados y parámetros de límite."""

from __future__ import annotations

from src.utils.chunking import chunkear_markdown


_SIMPLE_MD = """\
# Sección uno

Contenido de la primera sección con texto suficiente para ser un chunk.

## Subsección 1.1

Más contenido bajo la primera sección.

# Sección dos

Información de la segunda sección completamente distinta.
"""


def test_texto_vacio_devuelve_lista_vacia():
    assert chunkear_markdown("") == []
    assert chunkear_markdown("   ") == []


def test_produce_chunks_no_vacios():
    chunks = chunkear_markdown(_SIMPLE_MD)
    assert len(chunks) >= 1
    assert all(c.strip() for c in chunks)


def test_respeta_max_chunks():
    # Documento con muchas secciones
    md = "\n\n".join(f"## Sección {i}\n\n{'x' * 100}" for i in range(20))
    chunks = chunkear_markdown(md, max_chunks=5)
    assert len(chunks) <= 5


def test_secciones_grandes_se_subdividen():
    # Una sola sección > 900 chars debe generar varios chunks
    big_section = "# Título\n\n" + ("palabra " * 300)  # ~2400 chars
    chunks = chunkear_markdown(big_section, max_chars=900, overlap=150)
    assert len(chunks) >= 2
    assert all(len(c) <= 900 for c in chunks)


def test_preambulo_sin_encabezado_se_incluye():
    md = "Texto de introducción sin encabezado.\n\n# Primera sección\n\nContenido."
    chunks = chunkear_markdown(md)
    texto_unido = " ".join(chunks)
    assert "Texto de introducción" in texto_unido


def test_secciones_cortas_se_fusionan():
    # Dos secciones con poco texto deberían fusionarse
    md = "## A\n\ncorto\n\n## B\n\ntambién corto\n\n## C\n\nesto es más largo con suficiente texto para ser un chunk real."
    chunks = chunkear_markdown(md)
    # No debe haber chunks de un solo caracter o micro-fragmentos
    assert all(len(c) >= 10 for c in chunks)


def test_fixture_ciberseguridad_genera_chunks_coherentes(tmp_path):
    """Verifica que el fixture real produce múltiples chunks, uno por sección."""
    import pathlib
    fixture = pathlib.Path(__file__).parent.parent / "data" / "ejemplos" / "intro-ciberseguridad.md"
    if not fixture.exists():
        import pytest
        pytest.skip("fixture no disponible")

    texto = fixture.read_text(encoding="utf-8")
    chunks = chunkear_markdown(texto, max_chars=900, overlap=150)

    assert len(chunks) >= 4  # al menos una sección principal por chunk
    # Cada chunk debe tener contenido real
    assert all(len(c.strip()) >= 50 for c in chunks)
    # El chunk de VPN debe contener ProtonVPN
    vpn_chunks = [c for c in chunks if "ProtonVPN" in c]
    assert len(vpn_chunks) >= 1, "El chunk de VPN debe existir y mencionar ProtonVPN"
    # Ningún chunk debe mencionar NordVPN (no está en el fixture)
    for c in chunks:
        assert "NordVPN" not in c, f"NordVPN no debe aparecer en ningún chunk: {c[:100]}"
