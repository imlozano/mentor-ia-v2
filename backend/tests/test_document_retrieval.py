"""Tests unitarios de DocumentRetrievalService."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from src.services.document_retrieval import (
    DocumentRetrievalService,
    detect_intent,
    pick_representative_indices,
)
from src.utils.document_id import compute_document_id, derive_document_id

SESSION = str(uuid.uuid4())
DOC = "intro-ciberseguridad.md"
DOC_ID = compute_document_id(SESSION, DOC)


def test_detect_intent_summary():
    assert detect_intent("Explícame el documento", "auto") == "summary"


def test_detect_intent_specific():
    assert detect_intent("¿Qué es la atención multi-cabeza?", "auto") == "specific"


def test_pick_representative_indices():
    assert pick_representative_indices(10, 5) == [0, 2, 4, 7, 9]


def test_derive_document_id_legacy():
    payload = {"nombre_archivo": DOC, "source_path": "./data/uploads/x.md"}
    assert derive_document_id(payload, SESSION) == compute_document_id(SESSION, DOC)


class MiniQdrant:
    def __init__(self):
        self.points = [
            SimpleNamespace(
                payload={
                    "texto": f"chunk {i}",
                    "chunk_index": i,
                    "nombre_archivo": DOC,
                    "document_id": DOC_ID,
                    "session_id": SESSION,
                    "tipo_fuente": "md",
                }
            )
            for i in range(6)
        ]

    async def scroll_all(self, batch=256, session_id=None):
        for p in self.points:
            if p.payload["session_id"] == session_id:
                yield p

    async def scroll_by_document(self, session_id, document_id, nombre_archivo=None, batch=256):
        for p in self.points:
            pl = p.payload
            if pl["session_id"] == session_id and pl["document_id"] == document_id:
                yield p


@pytest.mark.asyncio
async def test_resolve_filename_to_document_id():
    svc = DocumentRetrievalService(MiniQdrant())
    docs = await svc.list_session_documents(SESSION)
    resolved = svc.resolve_document_id(
        "Explícame intro-ciberseguridad.md", docs, None
    )
    assert resolved == DOC_ID


@pytest.mark.asyncio
async def test_representative_chunks_count():
    svc = DocumentRetrievalService(MiniQdrant())
    chunks = await svc.get_representative_chunks(SESSION, DOC_ID, DOC, n=5)
    assert len(chunks) == 5
