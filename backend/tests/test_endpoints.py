"""Tests de endpoints: aislamiento por session_id y rate limiting.

Usan TestClient con los agentes/servicios reemplazados por dobles, de modo
que no se hace ninguna llamada de red a OpenAI ni a Qdrant.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.models import QueryResponse


class FakeAgenteRespuesta:
    """Doble del agente de respuesta; registra el session_id recibido."""

    def __init__(self) -> None:
        self.session_ids: list[str | None] = []

    async def responder(self, pregunta, historial=None, top_k=5, umbral_score=0.55, session_id=None):
        self.session_ids.append(session_id)
        return QueryResponse(
            respuesta="respuesta de prueba",
            origen="modelo",
            fuentes=[],
            detalle_origen=None,
        )


class FakeQdrant:
    """Doble del cliente Qdrant; registra el session_id de cada scroll."""

    def __init__(self, records) -> None:
        self._records = records
        self.scroll_session_ids: list[str | None] = []

    def scroll_all(self, batch: int = 256, session_id=None):
        self.scroll_session_ids.append(session_id)
        return self._async_iter()

    async def _async_iter(self):
        for record in self._records:
            yield record

    async def close(self) -> None:
        # Lo invoca el teardown del lifespan al cerrar el TestClient.
        return None


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _uuid() -> str:
    return str(uuid.uuid4())


# ───────────────────────── X-Session-ID requerido ─────────────────────────


def test_query_sin_session_id_devuelve_400(client):
    res = client.post("/query", json={"pregunta": "hola"})
    assert res.status_code == 400
    assert "X-Session-ID" in res.json()["detail"]


def test_query_con_session_id_invalido_devuelve_400(client):
    res = client.post(
        "/query",
        json={"pregunta": "hola"},
        headers={"X-Session-ID": "no-es-uuid"},
    )
    assert res.status_code == 400


def test_documentos_indexados_sin_session_id_devuelve_400(client):
    res = client.get("/documentos-indexados")
    assert res.status_code == 400


# ───────────────────────── Filtrado por session_id ─────────────────────────


def test_query_pasa_session_id_al_agente(client):
    fake = FakeAgenteRespuesta()
    app.state.agente_respuesta = fake
    sid = _uuid()

    res = client.post(
        "/query", json={"pregunta": "hola"}, headers={"X-Session-ID": sid}
    )

    assert res.status_code == 200
    assert fake.session_ids == [sid]


def test_query_acepta_historial_opcional(client):
    """Retrocompat: body sin historial sigue en 200; con historial también."""
    fake = FakeAgenteRespuesta()
    app.state.agente_respuesta = fake
    sid = _uuid()
    headers = {"X-Session-ID": sid}

    res_sin = client.post("/query", json={"pregunta": "hola"}, headers=headers)
    assert res_sin.status_code == 200

    res_con = client.post(
        "/query",
        json={
            "pregunta": "¿y eso?",
            "historial": [
                {"role": "user", "content": "¿Cómo protegerme en redes públicas?"},
                {"role": "agent", "content": "Usa VPN y 2FA."},
            ],
        },
        headers=headers,
    )
    assert res_con.status_code == 200


def test_documentos_indexados_filtra_por_session_id(client):
    records = [
        SimpleNamespace(
            payload={
                "source_path": "/data/a.pdf",
                "nombre_archivo": "a.pdf",
                "tipo_fuente": "pdf",
            }
        ),
        SimpleNamespace(
            payload={
                "source_path": "/data/a.pdf",
                "nombre_archivo": "a.pdf",
                "tipo_fuente": "pdf",
            }
        ),
    ]
    fake = FakeQdrant(records)
    app.state.qdrant = fake
    sid = _uuid()

    res = client.get("/documentos-indexados", headers={"X-Session-ID": sid})

    assert res.status_code == 200
    assert fake.scroll_session_ids == [sid]
    body = res.json()
    assert body["total_documentos"] == 1
    assert body["total_chunks"] == 2
    # source_path no debe filtrarse al cliente.
    assert "source_path" not in body["documentos"][0]


# ───────────────────────── Rate limiting ─────────────────────────


def test_query_dispara_429_al_exceder_limite(client):
    app.state.agente_respuesta = FakeAgenteRespuesta()
    sid = _uuid()  # misma sesión → mismo bucket de rate limit
    headers = {"X-Session-ID": sid}

    # Límite configurado en conftest: 5/minute.
    codes = [
        client.post("/query", json={"pregunta": "p"}, headers=headers).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429
