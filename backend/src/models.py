from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class MensajeHistorial(BaseModel):
    role: Literal["user", "agent"]
    content: str = Field(..., max_length=4000)


class QueryRequest(BaseModel):
    pregunta: str = Field(..., min_length=1, max_length=5000)
    historial: list[MensajeHistorial] = Field(default_factory=list, max_length=12)
    document_id: str | None = None
    modo: Literal["auto", "documento", "general"] = "auto"


class PlanRepasoRequest(BaseModel):
    tema: str = Field(..., min_length=1, max_length=500)
    fecha_inicio: date
    email: EmailStr | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    qdrant_ok: bool
    openai_ok: bool


class Fuente(BaseModel):
    archivo: str
    chunk_index: int
    score: float | None = None
    excerpt: str


class QueryResponse(BaseModel):
    respuesta: str
    origen: Literal["rag", "modelo"]
    fuentes: list[Fuente]
    detalle_origen: str | None = None


class SesionPlan(BaseModel):
    tipo: Literal["D+1", "D+7", "D+14", "D+30"]
    fecha: date
    titulo: str
    descripcion: list[str]


class PlanRepasoResponse(BaseModel):
    tema: str
    fecha_inicio: date
    sesiones: list[SesionPlan]
    email_enviado: bool
    chunks_ingresados: int | None = None


class OcrResponse(BaseModel):
    texto: str
    caracteres: int


class DocumentoIndexado(BaseModel):
    document_id: str
    nombre_archivo: str
    tipo_fuente: Literal["pdf", "txt", "md", "image"]
    total_chunks: int


class DocumentosResponse(BaseModel):
    documentos: list[DocumentoIndexado]
    total_chunks: int
    total_documentos: int


class UploadResponse(BaseModel):
    status: Literal["ok"]
    archivo: str
    chunks_ingresados: int
    document_id: str | None = None
    aviso: str | None = None


class DeleteDocumentoResponse(BaseModel):
    status: Literal["ok"]
    document_id: str
    nombre_archivo: str
    chunks_eliminados: int
    archivo_local_eliminado: bool


class VaciarDocumentosResponse(BaseModel):
    status: Literal["ok"]
    documentos_eliminados: int
    chunks_eliminados: int
    archivos_locales_eliminados: int
