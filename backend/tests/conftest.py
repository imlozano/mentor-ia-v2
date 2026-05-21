"""Configuración compartida de pytest.

Define variables de entorno dummy ANTES de que se importe `src.app`, para que
`Settings` se construya sin claves reales y los tests no toquen servicios
externos. Los límites de rate limiting se bajan para poder provocar un 429
con pocas peticiones.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QDRANT_API_KEY", "test-key")
os.environ.setdefault("QDRANT_COLLECTION", "test_collection")
os.environ.setdefault("MAKE_WEBHOOK_URL", "http://localhost/webhook")
os.environ.setdefault("RATE_LIMIT_QUERY", "5/minute")
os.environ.setdefault("RATE_LIMIT_UPLOAD", "5/minute")
os.environ.setdefault("RATE_LIMIT_PLAN", "5/minute")
os.environ.setdefault("RATE_LIMIT_OCR", "5/minute")
os.environ.setdefault("RATE_LIMIT_DELETE_IP", "5/minute")
os.environ.setdefault("RATE_LIMIT_OCR_IP", "5/minute")
os.environ.setdefault("RATE_LIMIT_PLAN_IP", "5/minute")
os.environ.setdefault("RATE_LIMIT_UPLOAD_IP", "5/minute")
os.environ.setdefault("RATE_LIMIT_QUERY_IP", "1000/minute")
os.environ.setdefault("RATE_LIMIT_DELETE", "5/minute")


@pytest.fixture(autouse=True)
def _reset_rate_limiter_after_test():
    """Evita que tests de 429 dejen el limiter activo para el resto."""
    yield
    from src.app import app

    app.state.limiter.enabled = False
    storage = getattr(app.state.limiter, "_storage", None)
    if storage is not None and hasattr(storage, "storage"):
        storage.storage.clear()
