"""Tests de saneado de nombres de archivo."""

from __future__ import annotations

from src.utils.safe_filename import safe_filename


def test_nombre_normal_se_conserva():
    assert safe_filename("documento.pdf") == "documento.pdf"


def test_espacios_se_sustituyen():
    assert safe_filename("documento normal.pdf") == "documento_normal.pdf"


def test_path_traversal_posix_se_neutraliza():
    out = safe_filename("../../etc/passwd")
    assert "/" not in out
    assert ".." not in out
    assert out == "passwd"


def test_path_traversal_windows_se_neutraliza():
    out = safe_filename("..\\..\\windows\\system32\\config.sys")
    assert "\\" not in out
    assert out.endswith("config.sys")


def test_archivo_oculto_pierde_punto_inicial():
    assert not safe_filename(".env").startswith(".")


def test_nombre_vacio_devuelve_placeholder():
    assert safe_filename("") == "archivo_sin_nombre"


def test_solo_caracteres_invalidos_devuelve_placeholder():
    assert safe_filename("///") == "archivo_sin_nombre"


def test_truncado_preserva_extension():
    out = safe_filename("a" * 300 + ".pdf")
    assert len(out) <= 200
    assert out.endswith(".pdf")
