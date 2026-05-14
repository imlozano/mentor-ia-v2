import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel
from starlette.responses import Response

from src.logger import setup_logging
from src.settings import get_settings

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.bind(version=VERSION, cors_origins=settings.cors_origins).info(
        "Mentor IA backend iniciado"
    )
    yield
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
async def health() -> HealthResponse:
    # En Fase 1 devolvemos siempre False. Fase 2 verificará Qdrant y Gemini
    # con un ping liviano y reflejará el estado real.
    return HealthResponse(
        status="ok",
        version=VERSION,
        qdrant_ok=False,
        gemini_ok=False,
    )
