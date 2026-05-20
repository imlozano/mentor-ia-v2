"""Tests del tope de páginas para OCR de PDF escaneado."""

from __future__ import annotations

from src.agentes.agente_extraccion import _cap_pdf_pages


def test_pdf_dentro_del_limite_no_se_trunca():
    paginas, aviso = _cap_pdf_pages(total=10, limite=20)
    assert paginas == 10
    assert aviso is None


def test_pdf_en_el_limite_exacto_no_se_trunca():
    paginas, aviso = _cap_pdf_pages(total=20, limite=20)
    assert paginas == 20
    assert aviso is None


def test_pdf_sobre_el_limite_se_trunca_con_aviso():
    paginas, aviso = _cap_pdf_pages(total=500, limite=20)
    assert paginas == 20
    assert aviso is not None
    assert "20" in aviso and "500" in aviso


def test_limite_cero_no_trunca():
    # Un límite no positivo se interpreta como "sin tope".
    paginas, aviso = _cap_pdf_pages(total=999, limite=0)
    assert paginas == 999
    assert aviso is None
