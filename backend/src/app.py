import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel
from starlette.responses import Response

from src.logger import setup_logging
from src.services.gemini import GeminiService
from src.services.make_webhook import MakeWebhookService
from src.services.qdrant_client import QdrantService
from src.services.vision import VisionService
from src.settings import get_settings

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()

    app.state.gemini = GeminiService(settings)
    app.state.qdrant = QdrantService(settings)
    app.state.vision = VisionService(settings)
    app.state.make = MakeWebhookService(settings)

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
            app.state.vision.close(),
            app.state.make.close(),
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


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    qdrant_ok: bool
    gemini_ok: bool


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    # Verificamos Qdrant y Gemini en paralelo con timeout 2s cada uno.
    # /health NUNCA falla por dependencias caídas: refleja estado real para
    # que el frontend pueda mostrar el badge de degradación.
    qdrant: QdrantService = request.app.state.qdrant
    gemini: GeminiService = request.app.state.gemini

    qdrant_ok, gemini_ok = await asyncio.gather(
        qdrant.ping(timeout=2.0),
        gemini.ping(timeout=2.0),
    )

    return HealthResponse(
        status="ok",
        version=VERSION,
        qdrant_ok=qdrant_ok,
        gemini_ok=gemini_ok,
    )
