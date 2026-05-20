"""Configuración compartida de pytest.

Define variables de entorno dummy ANTES de que se importe `src.app`, para que
`Settings` se construya sin claves reales y los tests no toquen servicios
externos. Los límites de rate limiting se bajan para poder provocar un 429
con pocas peticiones.
"""

from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QDRANT_API_KEY", "test-key")
os.environ.setdefault("QDRANT_COLLECTION", "test_collection")
os.environ.setdefault("MAKE_WEBHOOK_URL", "http://localhost/webhook")
os.environ.setdefault("RATE_LIMIT_QUERY", "5/minute")
os.environ.setdefault("RATE_LIMIT_UPLOAD", "5/minute")
os.environ.setdefault("RATE_LIMIT_PLAN", "5/minute")
os.environ.setdefault("RATE_LIMIT_OCR", "5/minute")
