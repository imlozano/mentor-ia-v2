"""Tests Sprint 2: DELETE documentos, vaciar sesión, retención local, rate limit IP."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.agentes.agente_extraccion import AgenteExtraccion
from src.app import app
from src.models import QueryResponse
from src.services.document_admin import DocumentAdminService
from src.services.document_retrieval import DocumentRetrievalService
from src.settings import Settings
from src.utils.document_id import compute_document_id


def _uuid() -> str:
    return str(uuid.uuid4())


def _record(session_id: str, document_id: str, nombre: str, idx: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{session_id}-{document_id}-{idx}",
        payload={
            "session_id": session_id,
            "document_id": document_id,
            "nombre_archivo": nombre,
            "source_path": f"./data/uploads/{nombre}",
            "tipo_fuente": "pdf",
            "chunk_index": idx,
            "texto": f"chunk {idx}",
        },
    )


class TrackingQdrant:
    def __init__(self, points: list[SimpleNamespace]) -> None:
        self.points = list(points)
        self.deleted_docs: list[tuple[str, str]] = []
        self.deleted_sessions: list[str] = []

    async def scroll_all(self, batch=256, session_id=None):
        for p in self.points:
            if session_id is None or p.payload.get("session_id") == session_id:
                yield p

    async def scroll_by_document(self, session_id, document_id, nombre_archivo=None, batch=256):
        for p in self.points:
            pl = p.payload
            if pl.get("session_id") != session_id:
                continue
            if pl.get("document_id") == document_id:
                yield p

    async def delete_by_document(self, session_id, document_id, nombre_archivo=None):
        self.deleted_docs.append((session_id, document_id))
        self.points = [
            p
            for p in self.points
            if not (
                p.payload.get("session_id") == session_id
                and p.payload.get("document_id") == document_id
            )
        ]

    async def delete_by_session(self, session_id: str) -> None:
        self.deleted_sessions.append(session_id)
        self.points = [p for p in self.points if p.payload.get("session_id") != session_id]

    async def upsert_points(self, points) -> None:
        self.points.extend(
            [SimpleNamespace(id=str(i), payload=pt.payload) for i, pt in enumerate(points)]
        )

    async def close(self) -> None:
        return None


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _wire_admin(qdrant: TrackingQdrant) -> None:
    settings = Settings(
        openai_api_key="k",
        qdrant_url="http://localhost",
        qdrant_api_key="k",
    )
    retrieval = DocumentRetrievalService(qdrant)  # type: ignore[arg-type]
    app.state.qdrant = qdrant  # type: ignore[assignment]
    app.state.document_retrieval = retrieval
    app.state.document_admin = DocumentAdminService(qdrant, retrieval, settings)  # type: ignore[arg-type]


def test_delete_documento_sin_session_id_devuelve_400(client):
    res = client.delete(f"/documentos/{_uuid()}")
    assert res.status_code == 400


def test_delete_documento_inexistente_devuelve_404(client):
    sid = _uuid()
    qdrant = TrackingQdrant([])
    _wire_admin(qdrant)
    res = client.delete(
        f"/documentos/{_uuid()}",
        headers={"X-Session-ID": sid},
    )
    assert res.status_code == 404


def test_delete_documento_otra_sesion_devuelve_404_y_no_borra(client):
    sid_a = _uuid()
    sid_b = _uuid()
    nombre = "shared.pdf"
    doc_b = compute_document_id(sid_b, nombre)
    qdrant = TrackingQdrant([_record(sid_b, doc_b, nombre)])
    _wire_admin(qdrant)

    res = client.delete(
        f"/documentos/{doc_b}",
        headers={"X-Session-ID": sid_a},
    )
    assert res.status_code == 404
    assert len(qdrant.points) == 1
    assert qdrant.deleted_docs == []


def test_delete_documento_propio_borra_solo_su_sesion(client):
    sid = _uuid()
    nombre = "a.pdf"
    doc_id = compute_document_id(sid, nombre)
    sid_other = _uuid()
    doc_other = compute_document_id(sid_other, "b.pdf")
    qdrant = TrackingQdrant(
        [
            _record(sid, doc_id, nombre, 0),
            _record(sid, doc_id, nombre, 1),
            _record(sid_other, doc_other, "b.pdf", 0),
        ]
    )
    _wire_admin(qdrant)

    res = client.delete(
        f"/documentos/{doc_id}",
        headers={"X-Session-ID": sid},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["document_id"] == doc_id
    assert body["chunks_eliminados"] == 2
    assert qdrant.deleted_docs == [(sid, doc_id)]
    assert len(qdrant.points) == 1
    assert qdrant.points[0].payload["session_id"] == sid_other


def test_vaciar_documentos_no_afecta_otra_sesion(client):
    sid_a = _uuid()
    sid_b = _uuid()
    doc_a = compute_document_id(sid_a, "a.pdf")
    doc_b = compute_document_id(sid_b, "b.pdf")
    qdrant = TrackingQdrant(
        [
            _record(sid_a, doc_a, "a.pdf"),
            _record(sid_b, doc_b, "b.pdf"),
        ]
    )
    _wire_admin(qdrant)

    res = client.delete("/documentos", headers={"X-Session-ID": sid_a})
    assert res.status_code == 200
    assert res.json()["documentos_eliminados"] == 1
    assert qdrant.deleted_sessions == [sid_a]
    assert len(qdrant.points) == 1
    assert qdrant.points[0].payload["session_id"] == sid_b


def test_vaciar_documentos_sin_session_id_devuelve_400(client):
    res = client.delete("/documentos")
    assert res.status_code == 400


def test_rate_limit_ip_no_evadible_rotando_session_id(client):
    app.state.limiter.enabled = True
    if hasattr(app.state.limiter, "_storage"):
        app.state.limiter._storage.storage.clear()
    class FakeAgenteRespuesta:
        async def responder(self, **kwargs):
            return QueryResponse(respuesta="ok", origen="modelo", fuentes=[])

    from src import app as app_module
    app_module.settings.rate_limit_query_ip = "5/minute"
    app_module.settings.rate_limit_query = "1000/minute"
    app.state.agente_respuesta = FakeAgenteRespuesta()
    sids = [_uuid() for _ in range(6)]
    codes = [
        client.post(
            "/query",
            json={"pregunta": "p"},
            headers={"X-Session-ID": sid},
        ).status_code
        for sid in sids
    ]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429


def test_unlink_tras_ingesta_exitosa():
    settings = Settings(
        openai_api_key="k",
        qdrant_url="http://localhost",
        qdrant_api_key="k",
    )
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / "test-ingest.txt"
    path.write_text("hola mundo " * 50, encoding="utf-8")
    sid = _uuid()

    qdrant = TrackingQdrant([])
    openai = AsyncMock()
    openai.embed_texts = AsyncMock(return_value=[[0.1] * 768])

    agente = AgenteExtraccion(qdrant, openai, settings)  # type: ignore[arg-type]
    import asyncio

    async def run():
        return await agente.ingestar_documento(path, sid)

    result = asyncio.run(run())
    assert result.chunks_ingresados > 0
    assert not path.exists()


def test_no_unlink_si_upsert_falla():
    settings = Settings(
        openai_api_key="k",
        qdrant_url="http://localhost",
        qdrant_api_key="k",
    )
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / "test-fail.txt"
    path.write_text("contenido " * 50, encoding="utf-8")
    sid = _uuid()

    qdrant = TrackingQdrant([])

    async def fail_upsert(_points):
        raise RuntimeError("qdrant down")

    qdrant.upsert_points = fail_upsert  # type: ignore[method-assign]

    openai = AsyncMock()
    openai.embed_texts = AsyncMock(return_value=[[0.1] * 768])
    agente = AgenteExtraccion(qdrant, openai, settings)  # type: ignore[arg-type]

    import asyncio

    with pytest.raises(RuntimeError):
        asyncio.run(agente.ingestar_documento(path, sid))
    assert path.exists()


def test_resubida_reemplaza_chunks_previos():
    settings = Settings(
        openai_api_key="k",
        qdrant_url="http://localhost",
        qdrant_api_key="k",
    )
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / "resubida.txt"
    path.write_text("contenido de prueba " * 80, encoding="utf-8")
    sid = _uuid()

    qdrant = TrackingQdrant([])
    openai = AsyncMock()
    openai.embed_texts = AsyncMock(return_value=[[0.1] * 768, [0.2] * 768])

    agente = AgenteExtraccion(qdrant, openai, settings)  # type: ignore[arg-type]
    import asyncio

    asyncio.run(agente.ingestar_documento(path, sid))
    first_deletes = len(qdrant.deleted_docs)

    path.write_text("contenido actualizado " * 80, encoding="utf-8")
    asyncio.run(agente.ingestar_documento(path, sid))
    assert len(qdrant.deleted_docs) == first_deletes + 1
    assert qdrant.deleted_docs[-1][0] == sid
