"""Tests de la política de validación de archivos."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.settings import get_settings
from src.utils.upload_policy import enforce_size, validate_upload

settings = get_settings()


def test_extension_soportada_devuelve_nombre_saneado():
    assert validate_upload("apuntes.pdf", 1000, settings) == "apuntes.pdf"
    assert validate_upload("notas.txt", 1000, settings) == "notas.txt"


def test_extension_no_soportada_lanza_400():
    with pytest.raises(HTTPException) as exc:
        validate_upload("malware.exe", 1000, settings)
    assert exc.value.status_code == 400


def test_pdf_demasiado_grande_lanza_400():
    with pytest.raises(HTTPException) as exc:
        validate_upload("grande.pdf", settings.max_pdf_bytes + 1, settings)
    assert exc.value.status_code == 400


def test_txt_demasiado_grande_lanza_400():
    with pytest.raises(HTTPException) as exc:
        validate_upload("grande.txt", settings.max_text_bytes + 1, settings)
    assert exc.value.status_code == 400


def test_imagen_demasiado_grande_lanza_400():
    with pytest.raises(HTTPException) as exc:
        validate_upload("foto.png", settings.max_image_bytes + 1, settings)
    assert exc.value.status_code == 400


def test_size_none_no_falla_en_validate():
    # Sin Content-Length la validación de tamaño se aplaza a enforce_size.
    assert validate_upload("apuntes.pdf", None, settings) == "apuntes.pdf"


def test_enforce_size_rechaza_contenido_excesivo():
    contenido = b"x" * (settings.max_text_bytes + 1)
    with pytest.raises(HTTPException) as exc:
        enforce_size(".txt", contenido, settings)
    assert exc.value.status_code == 400


def test_enforce_size_acepta_contenido_valido():
    enforce_size(".txt", b"contenido pequeno", settings)  # no lanza
