import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.responses import Response

from src.agentes.agente_extraccion import AgenteExtraccion
from src.agentes.agente_plan_repaso import AgentePlanRepaso
from src.agentes.agente_respuesta import AgenteRespuesta
from src.logger import setup_logging
from src.models import (
    DocumentoIndexado,
    DocumentosResponse,
    HealthResponse,
    OcrResponse,
    PlanRepasoRequest,
    PlanRepasoResponse,
    QueryRequest,
    QueryResponse,
    UploadResponse,
)
from src.services.make_webhook import MakeWebhookService
from src.services.openai_service import OpenAIService
from src.services.qdrant_client import QdrantService
from src.settings import get_settings

VERSION = "0.1.0"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PDF_BYTES = 25 * 1024 * 1024
SUPPORTED_UPLOAD_EXTENSIONS = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()

    app.state.openai = OpenAIService(settings)
    app.state.qdrant = QdrantService(settings)
    app.state.make = MakeWebhookService(settings)
    app.state.agente_extraccion = AgenteExtraccion(
        qdrant_client=app.state.qdrant,
        openai_service=app.state.openai,
        settings=settings,
    )
    app.state.agente_respuesta = AgenteRespuesta(
        qdrant_client=app.state.qdrant,
        openai_service=app.state.openai,
    )
    app.state.agente_plan_repaso = AgentePlanRepaso(
        qdrant_client=app.state.qdrant,
        openai_service=app.state.openai,
        agente_extraccion=app.state.agente_extraccion,
        make_webhook=app.state.make,
    )

    logger.bind(version=VERSION, cors_origins=settings.cors_origins).info(
        "Mentor IA backend iniciando"
    )

    # ensure_collection es idempotente: si la colección ya existe, no-op.
    # Si Qdrant está caído, lo logueamos pero NO impedimos el arranque para
    # que /health pueda reflejar el estado real (qdrant_ok=false).
    try:
        await app.state.qdrant.ensure_collection()
    except Exception as exc:  # noqa: BLE001
        logger.error("qdrant: ensure_collection falló al arranque: {!r}", exc)

    logger.info("Mentor IA backend listo")
    try:
        yield
    finally:
        await asyncio.gather(
            app.state.qdrant.close(),
            app.state.make.close(),
            app.state.openai.close(),
            return_exceptions=True,
        )
        logger.info("Mentor IA backend detenido")


app = FastAPI(
    title="Mentor IA API",
    version=VERSION,
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


_MAX_REQUEST_ID_LEN = 36


def _parse_or_generate_request_id(raw: str | None) -> tuple[str, str]:
    """Devuelve (request_id, source). source ∈ {'forwarded', 'generated'}.

    Solo se acepta un header X-Request-ID si es un UUIDv4 válido y tiene
    longitud razonable. Cualquier otra cosa se descarta y se genera uno
    nuevo, evitando que un cliente inyecte texto arbitrario en los logs.
    """
    if raw and len(raw) <= _MAX_REQUEST_ID_LEN:
        try:
            parsed = uuid.UUID(raw)
            if parsed.version == 4:
                return str(parsed), "forwarded"
        except (ValueError, AttributeError):
            pass
    return str(uuid.uuid4()), "generated"


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    raw = request.headers.get("X-Request-ID")
    request_id, source = _parse_or_generate_request_id(raw)
    request.state.request_id = request_id

    with logger.contextualize(request_id=request_id, request_id_source=source):
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    # SMOKE TEST ROLLBACK — rotura intencional para validar el rollback
    # automático del pipeline CI/CD. Se revierte inmediatamente después.
    raise RuntimeError("smoke test rollback — rotura intencional")
    # Verificamos Qdrant y OpenAI (chat + vision + embeddings) en paralelo
    # con timeout 2s cada uno. /health NUNCA falla por dependencias caídas:
    # refleja estado real para que el frontend muestre degradación.
    qdrant: QdrantService = request.app.state.qdrant
    openai: OpenAIService = request.app.state.openai

    qdrant_ok, openai_ok = await asyncio.gather(
        qdrant.ping(timeout=2.0),
        openai.ping(timeout=2.0),
    )

    return HealthResponse(
        status="ok",
        version=VERSION,
        qdrant_ok=qdrant_ok,
        openai_ok=openai_ok,
    )


@app.post("/upload-document", response_model=UploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    x_filename: str | None = Header(default=None),
) -> UploadResponse:
    from src.utils.safe_filename import safe_filename

    suggested_name = x_filename or file.filename or "archivo_sin_nombre"
    safe_name = safe_filename(suggested_name)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Extensión no soportada: {suffix}")

    content = await file.read()
    if suffix in IMAGE_EXTENSIONS and len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Imagen supera tamaño máximo de 10 MB")
    if suffix == ".pdf" and len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="PDF supera tamaño máximo de 25 MB")

    docs_dir = settings.base_docs_dir
    docs_dir.mkdir(parents=True, exist_ok=True)
    target_path = docs_dir / safe_name
    target_path.write_bytes(content)

    agente_extraccion: AgenteExtraccion = request.app.state.agente_extraccion
    chunks_ingresados = await agente_extraccion.ingestar_documento(target_path)

    return UploadResponse(status="ok", archivo=safe_name, chunks_ingresados=chunks_ingresados)


@app.get("/documentos-indexados", response_model=DocumentosResponse)
async def documentos_indexados(request: Request) -> DocumentosResponse:
    qdrant: QdrantService = request.app.state.qdrant
    grouped: dict[str, dict[str, int | str]] = {}
    total_chunks = 0

    async for record in qdrant.scroll_all():
        payload = record.payload or {}
        source_path = str(payload.get("source_path") or "")
        if not source_path:
            continue

        entry = grouped.setdefault(
            source_path,
            {
                "nombre_archivo": str(payload.get("nombre_archivo") or Path(source_path).name),
                "source_path": source_path,
                "tipo_fuente": str(payload.get("tipo_fuente") or "txt"),
                "total_chunks": 0,
            },
        )
        entry["total_chunks"] = int(entry["total_chunks"]) + 1
        total_chunks += 1

    documentos = [
        DocumentoIndexado(
            nombre_archivo=str(item["nombre_archivo"]),
            source_path=str(item["source_path"]),
            tipo_fuente=str(item["tipo_fuente"]),
            total_chunks=int(item["total_chunks"]),
        )
        for item in grouped.values()
    ]
    documentos.sort(key=lambda doc: doc.nombre_archivo.lower())

    return DocumentosResponse(
        documentos=documentos,
        total_chunks=total_chunks,
        total_documentos=len(documentos),
    )


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: Request, body: QueryRequest) -> QueryResponse:
    agente_respuesta: AgenteRespuesta = request.app.state.agente_respuesta
    try:
        return await agente_respuesta.responder(
            pregunta=body.pregunta,
            top_k=settings.rag_top_k,
            umbral_score=settings.rag_score_threshold,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("query failed: {!r}", exc)
        raise HTTPException(
            status_code=503,
            detail="No fue posible procesar la consulta por fallo en servicios externos.",
        ) from exc


@app.post("/plan-repaso", response_model=PlanRepasoResponse)
async def plan_repaso_endpoint(
    request: Request,
    file: UploadFile | None = File(default=None),
) -> PlanRepasoResponse:
    from src.utils.safe_filename import safe_filename

    agente_plan: AgentePlanRepaso = request.app.state.agente_plan_repaso
    content_type = request.headers.get("content-type", "")

    tema: str
    fecha_inicio: date
    email: str | None = None
    archivo_guardado: Path | None = None

    if content_type.startswith("application/json"):
        body = PlanRepasoRequest.model_validate(await request.json())
        tema = body.tema
        fecha_inicio = body.fecha_inicio
        email = str(body.email) if body.email else None
    else:
        form = await request.form()
        tema_raw = str(form.get("tema") or "").strip()
        fecha_raw = str(form.get("fecha_inicio") or "").strip()
        email_raw = str(form.get("email") or "").strip()
        if not tema_raw or not fecha_raw:
            raise HTTPException(
                status_code=400,
                detail="En modo multipart se requiere 'tema' y 'fecha_inicio'.",
            )
        try:
            fecha_inicio = date.fromisoformat(fecha_raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="fecha_inicio debe estar en formato YYYY-MM-DD.",
            ) from exc
        tema = tema_raw
        email = email_raw or None
        if file is not None:
            safe_name = safe_filename(file.filename or "documento_plan.pdf")
            docs_dir = settings.base_docs_dir
            docs_dir.mkdir(parents=True, exist_ok=True)
            archivo_guardado = docs_dir / safe_name
            archivo_guardado.write_bytes(await file.read())

    try:
        return await agente_plan.generar_plan(
            tema=tema,
            fecha_inicio=fecha_inicio,
            email=email,
            archivo=archivo_guardado,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("plan-repaso failed: {!r}", exc)
        raise HTTPException(
            status_code=503,
            detail="No fue posible generar el plan por fallo en servicios externos.",
        ) from exc


@app.post("/ocr-imagen", response_model=OcrResponse)
async def ocr_imagen_endpoint(request: Request, file: UploadFile = File(...)) -> OcrResponse:
    filename = file.filename or "imagen"
    suffix = Path(filename).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Solo se admiten imágenes PNG/JPG/JPEG.")

    content = await file.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Imagen supera tamaño máximo de 10 MB")

    mime = "image/png" if suffix == ".png" else "image/jpeg"
    openai_service: OpenAIService = request.app.state.openai
    try:
        texto = await openai_service.extract_text_from_image(content, mime=mime)
    except Exception as exc:  # noqa: BLE001
        logger.error("ocr-imagen failed: {!r}", exc)
        raise HTTPException(
            status_code=503,
            detail="No fue posible procesar OCR por fallo de OpenAI Vision.",
        ) from exc

    return OcrResponse(texto=texto, caracteres=len(texto))
