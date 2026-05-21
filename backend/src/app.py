import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse, Response

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
from src.utils.safe_filename import safe_filename
from src.utils.session_id import require_session_id
from src.utils.upload_policy import IMAGE_EXTENSIONS, enforce_size, validate_upload

VERSION = "0.1.0"

settings = get_settings()


def _write_upload_file(safe_name: str, content: bytes) -> Path:
    """Guarda un archivo subido en ``upload_dir`` (escribible por el usuario app)."""
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = upload_dir / safe_name
    try:
        target_path.write_bytes(content)
    except PermissionError as exc:
        logger.error("upload: sin permiso de escritura en {!r}: {!r}", target_path, exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "No se pudo guardar el archivo en el servidor. "
                "Vuelve a intentarlo; si persiste, contacta al administrador."
            ),
        ) from exc
    except OSError as exc:
        logger.error("upload: error de E/S en {!r}: {!r}", target_path, exc)
        raise HTTPException(
            status_code=503,
            detail="No se pudo guardar el archivo en el servidor.",
        ) from exc
    return target_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

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
        settings=settings,
    )
    app.state.agente_plan_repaso = AgentePlanRepaso(
        qdrant_client=app.state.qdrant,
        openai_service=app.state.openai,
        agente_extraccion=app.state.agente_extraccion,
        make_webhook=app.state.make,
        settings=settings,
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


# ───────────────────────── Rate limiting ─────────────────────────
# Clave = IP + X-Session-ID: limita por origen real aunque varias sesiones
# compartan IP (NAT) y aunque un cliente rote el session_id manteniendo IP.
def _rate_limit_key(request: Request) -> str:
    ip = get_remote_address(request)
    sid = request.headers.get("X-Session-ID") or "anon"
    return f"{ip}:{sid}"


limiter = Limiter(key_func=_rate_limit_key, enabled=settings.rate_limit_enabled)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning("rate limit excedido: key={}", _rate_limit_key(request))
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Demasiadas solicitudes en poco tiempo. "
            "Espera un momento antes de reintentar."
        },
    )


app = FastAPI(
    title="Mentor IA API",
    version=VERSION,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

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
@limiter.limit(lambda: settings.rate_limit_upload)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    x_filename: str | None = Header(default=None),
    session_id: str = Depends(require_session_id),
) -> UploadResponse:
    suggested_name = x_filename or file.filename or "archivo_sin_nombre"
    # Valida extensión y, si el cliente envió Content-Length, tamaño.
    safe_name = validate_upload(suggested_name, file.size, settings)
    suffix = Path(safe_name).suffix.lower()

    content = await file.read()
    # Verificación de tamaño real (cubre clientes que no envían tamaño).
    enforce_size(suffix, content, settings)

    target_path = _write_upload_file(safe_name, content)

    agente_extraccion: AgenteExtraccion = request.app.state.agente_extraccion
    resultado = await agente_extraccion.ingestar_documento(target_path, session_id)

    return UploadResponse(
        status="ok",
        archivo=safe_name,
        chunks_ingresados=resultado.chunks_ingresados,
        aviso=resultado.aviso,
    )


@app.get("/documentos-indexados", response_model=DocumentosResponse)
async def documentos_indexados(
    request: Request,
    session_id: str = Depends(require_session_id),
) -> DocumentosResponse:
    qdrant: QdrantService = request.app.state.qdrant
    grouped: dict[str, dict[str, int | str]] = {}
    total_chunks = 0

    async for record in qdrant.scroll_all(session_id=session_id):
        payload = record.payload or {}
        source_path = str(payload.get("source_path") or "")
        if not source_path:
            continue

        entry = grouped.setdefault(
            source_path,
            {
                "nombre_archivo": str(payload.get("nombre_archivo") or Path(source_path).name),
                "tipo_fuente": str(payload.get("tipo_fuente") or "txt"),
                "total_chunks": 0,
            },
        )
        entry["total_chunks"] = int(entry["total_chunks"]) + 1
        total_chunks += 1

    documentos = [
        DocumentoIndexado(
            nombre_archivo=str(item["nombre_archivo"]),
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
@limiter.limit(lambda: settings.rate_limit_query)
async def query_endpoint(
    request: Request,
    body: QueryRequest,
    session_id: str = Depends(require_session_id),
) -> QueryResponse:
    agente_respuesta: AgenteRespuesta = request.app.state.agente_respuesta
    try:
        return await agente_respuesta.responder(
            pregunta=body.pregunta,
            historial=[m.model_dump() for m in body.historial],
            top_k=settings.rag_top_k,
            umbral_score=settings.rag_score_threshold,
            session_id=session_id,
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
@limiter.limit(lambda: settings.rate_limit_plan)
async def plan_repaso_endpoint(
    request: Request,
    file: UploadFile | None = File(default=None),
    session_id: str = Depends(require_session_id),
) -> PlanRepasoResponse:
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
            # Mismo control de extensión/tamaño que /upload-document.
            safe_name = validate_upload(file.filename or "documento_plan.pdf", file.size, settings)
            content = await file.read()
            enforce_size(Path(safe_name).suffix.lower(), content, settings)
            archivo_guardado = _write_upload_file(safe_name, content)

    try:
        return await agente_plan.generar_plan(
            tema=tema,
            fecha_inicio=fecha_inicio,
            email=email,
            archivo=archivo_guardado,
            session_id=session_id,
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
@limiter.limit(lambda: settings.rate_limit_ocr)
async def ocr_imagen_endpoint(request: Request, file: UploadFile = File(...)) -> OcrResponse:
    # /ocr-imagen no toca Qdrant: solo se limita por tasa, no requiere sesión.
    filename = file.filename or "imagen"
    suffix = Path(safe_filename(filename)).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Solo se admiten imágenes PNG/JPG/JPEG.")

    content = await file.read()
    enforce_size(suffix, content, settings)

    mime = "image/png" if suffix == ".png" else "image/jpeg"
    openai_service: OpenAIService = request.app.state.openai
    try:
        texto = await openai_service.extract_text_from_image(
            content, mime=mime, max_tokens=settings.openai_max_tokens_ocr
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("ocr-imagen failed: {!r}", exc)
        raise HTTPException(
            status_code=503,
            detail="No fue posible procesar OCR por fallo de OpenAI Vision.",
        ) from exc

    return OcrResponse(texto=texto, caracteres=len(texto))
