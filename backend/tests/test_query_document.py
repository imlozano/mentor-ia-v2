"""Tests P0: flujo documento listado → consulta → RAG documental."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.agentes.agente_respuesta import AgenteRespuesta
from src.app import app
from src.models import QueryResponse
from src.services.document_retrieval import DocumentRetrievalService
from src.settings import Settings
from src.utils.document_id import compute_document_id

SESSION = str(uuid.uuid4())
DOC_NAME = "attention-is-all-you-need.pdf"
DOCUMENT_ID = compute_document_id(SESSION, DOC_NAME)
SOURCE = f"./data/uploads/{DOC_NAME}"


def _payload(chunk_index: int, texto: str) -> dict:
    return {
        "texto": texto,
        "nombre_archivo": DOC_NAME,
        "chunk_index": chunk_index,
        "document_id": DOCUMENT_ID,
        "source_path": SOURCE,
        "session_id": SESSION,
        "tipo_fuente": "pdf",
    }


def _record(chunk_index: int, texto: str) -> SimpleNamespace:
    return SimpleNamespace(id=str(chunk_index), payload=_payload(chunk_index, texto))


def _scored(chunk_index: int, texto: str, score: float) -> SimpleNamespace:
    return SimpleNamespace(score=score, payload=_payload(chunk_index, texto))


class FakeOpenAI:
    async def embed_query(self, text: str) -> list[float]:
        return [0.1] * 768

    async def generate(self, prompt, system=None, max_tokens=None) -> str:
        return "Los Transformers usan mecanismos de atención multi-cabeza."

    async def close(self) -> None:
        pass


class FakeQdrant:
    """Simula Qdrant con scores bajos (<0.55) para reproducir el bug original."""

    def __init__(self) -> None:
        self.points = [
            _record(i, f"Chunk {i}: The Transformer architecture uses multi-head attention.")
            for i in range(8)
        ]
        self.deleted: list[tuple[str, str]] = []

    def _match_document(self, payload: dict, session_id: str | None, document_id: str | None, nombre_archivo: str | None) -> bool:
        if session_id and payload.get("session_id") != session_id:
            return False
        if document_id and payload.get("document_id") != document_id:
            if nombre_archivo and payload.get("nombre_archivo") != nombre_archivo:
                return False
            if not nombre_archivo:
                return False
        if nombre_archivo and not document_id and payload.get("nombre_archivo") != nombre_archivo:
            return False
        return True

    async def scroll_all(self, batch=256, session_id=None):
        for p in self.points:
            if session_id is None or p.payload.get("session_id") == session_id:
                yield p

    async def scroll_by_document(self, session_id, document_id, nombre_archivo=None, batch=256):
        for p in self.points:
            pl = p.payload
            if pl.get("session_id") != session_id:
                continue
            if pl.get("document_id") == document_id or pl.get("nombre_archivo") == nombre_archivo:
                yield p

    async def delete_by_document(self, session_id, document_id, nombre_archivo=None):
        self.deleted.append((session_id, document_id))
        self.points = [
            p
            for p in self.points
            if not (
                p.payload.get("session_id") == session_id
                and (
                    p.payload.get("document_id") == document_id
                    or p.payload.get("nombre_archivo") == nombre_archivo
                )
            )
        ]

    async def query(
        self,
        vector,
        limit,
        score_threshold=None,
        session_id=None,
        nombre_archivo=None,
        document_id=None,
        strict_document_filter=False,
    ):
        hits = []
        for p in self.points:
            pl = p.payload
            if session_id and pl.get("session_id") != session_id:
                continue
            if document_id and pl.get("document_id") != document_id:
                if strict_document_filter:
                    continue
            if nombre_archivo and pl.get("nombre_archivo") != nombre_archivo:
                continue
            hits.append(_scored(pl["chunk_index"], pl["texto"], 0.35))
        return hits[:limit]

    async def close(self) -> None:
        pass


@pytest.fixture
def settings():
    return Settings(
        openai_api_key="test",
        qdrant_url="http://localhost:6333",
        qdrant_api_key="test",
    )


@pytest.fixture
def agente(settings):
    qdrant = FakeQdrant()
    openai = FakeOpenAI()
    retrieval = DocumentRetrievalService(qdrant)
    agent = AgenteRespuesta(qdrant, openai, settings, retrieval)
    return agent, qdrant


@pytest.mark.asyncio
async def test_meta_archivo_responde_rag_con_documento_en_sesion(agente):
    """Baseline P0: pregunta meta-archivo con chunks en sesión debe usar RAG."""
    agent, _ = agente
    result = await agent.responder(
        pregunta="Explícame el documento attention-is-all-you-need.pdf",
        session_id=SESSION,
        umbral_score=0.55,
    )
    assert result.origen == "rag"
    assert len(result.fuentes) > 0
    assert all(f.archivo == DOC_NAME for f in result.fuentes)


@pytest.mark.asyncio
async def test_query_con_document_id_seleccionado(agente):
    agent, _ = agente
    result = await agent.responder(
        pregunta="Explícame este documento",
        session_id=SESSION,
        document_id=DOCUMENT_ID,
        umbral_score=0.55,
    )
    assert result.origen == "rag"
    assert result.fuentes


@pytest.mark.asyncio
async def test_pregunta_especifica_con_document_id_fallback(agente):
    agent, _ = agente
    result = await agent.responder(
        pregunta="¿Qué dice sobre transformers?",
        session_id=SESSION,
        document_id=DOCUMENT_ID,
        umbral_score=0.55,
    )
    assert result.origen == "rag"
    assert result.fuentes


@pytest.mark.asyncio
async def test_resuelve_documento_por_nombre_sin_seleccion(agente):
    agent, _ = agente
    result = await agent.responder(
        pregunta="Explícame attention-is-all-you-need.pdf",
        session_id=SESSION,
        umbral_score=0.55,
    )
    assert result.origen == "rag"


class FakeAgenteDocumental:
    async def responder(self, **kwargs):
        return QueryResponse(
            respuesta="ok",
            origen="rag",
            fuentes=[],
            detalle_origen="test",
        )


def test_endpoint_query_acepta_document_id():
    app.state.agente_respuesta = FakeAgenteDocumental()
    sid = str(uuid.uuid4())
    res = TestClient(app).post(
        "/query",
        json={
            "pregunta": "Explícame este documento",
            "document_id": str(uuid.uuid4()),
            "modo": "auto",
        },
        headers={"X-Session-ID": sid},
    )
    assert res.status_code == 200


def test_documentos_indexados_devuelve_document_id():
    records = [_record(0, "texto"), _record(1, "texto2")]
    fake = FakeQdrant()
    fake.points = records
    app.state.qdrant = fake
    sid = SESSION
    res = TestClient(app).get("/documentos-indexados", headers={"X-Session-ID": sid})
    assert res.status_code == 200
    body = res.json()
    assert body["total_documentos"] == 1
    assert body["documentos"][0]["document_id"] == DOCUMENT_ID
