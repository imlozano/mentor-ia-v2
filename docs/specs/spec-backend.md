# Spec — Backend FastAPI (`backend/`)

> Especificación técnica para construir el backend del sistema **Mentor
> IA**. Este documento lo lee el agente (Claude Code o Cursor) y produce
> el código en `backend/`.
>
> Cualquier ambigüedad se resuelve consultando antes
> [`../academic/Documento_Tecnico.md`](../academic/Documento_Tecnico.md)
> y [`../academic/Flujo_Interaccion_Usuario_Sistema.md`](../academic/Flujo_Interaccion_Usuario_Sistema.md).

---

## 1. Resumen

API REST con FastAPI que orquesta tres agentes (`AgenteExtraccion`,
`AgenteRespuesta`, `AgentePlanRepaso`) sobre una base vectorial Qdrant,
integra Google Gemini para LLM y embeddings, Google Cloud Vision para
OCR y Make.com para envío de correos.

Despliegue local con `docker compose up`. Despliegue producción en un
DigitalOcean Droplet con el mismo `docker-compose.yml`.

## 2. Estructura de archivos

```
backend/
├── docker-compose.yml              Servicio único `backend` en puerto 8000
├── Dockerfile                      Python 3.11-slim, multistage
├── pyproject.toml                  Dependencias (preferir uv o poetry)
├── .env.example                    Plantilla de variables de entorno
├── .gitignore
├── data/
│   └── ejemplos/                   Documentos subidos (PDF, TXT, MD, imágenes)
├── credentials/
│   └── vision.json                 Credencial GCP Vision (no commitear)
└── src/
    ├── __init__.py
    ├── app.py                      Endpoints FastAPI (entry point)
    ├── settings.py                 Configuración con pydantic-settings
    ├── models.py                   Pydantic schemas (request/response)
    ├── deps.py                     Dependencias inyectables (clientes Qdrant, Gemini, etc.)
    ├── agentes/
    │   ├── __init__.py
    │   ├── agente_extraccion.py
    │   ├── agente_respuesta.py
    │   └── agente_plan_repaso.py
    ├── services/
    │   ├── __init__.py
    │   ├── gemini.py               Wrapper de Google Gemini (LLM + embeddings)
    │   ├── vision.py               Wrapper de Google Cloud Vision
    │   ├── qdrant_client.py        Conexión a Qdrant Cloud + helpers
    │   └── make_webhook.py         Cliente del webhook de Make.com
    ├── utils/
    │   ├── __init__.py
    │   ├── chunking.py             Función pura para chunkear texto
    │   ├── pdf_reader.py           Wrapper de pypdf
    │   └── safe_filename.py        Sanitización de nombres de archivo subidos
    └── logger.py                   Configuración loguru
```

## 3. Dependencias

### 3.1 Dependencias de producción

Mínimas necesarias en `pyproject.toml` bajo `[project].dependencies`:

```
fastapi
uvicorn[standard]
pydantic>=2
pydantic-settings
python-multipart                  # uploads
httpx                             # cliente HTTP async
pypdf>=6.0
qdrant-client
google-genai                      # SDK oficial de Gemini
google-cloud-vision               # cliente Vision
loguru
python-dotenv                     # solo en dev
```

Versiones exactas que las defina el agente con `uv`, priorizando
estables más recientes.

### 3.2 Dependencias de desarrollo

Bajo `[dependency-groups.dev]` (o el grupo equivalente que use `uv`):

```
pip-audit                         # auditoría de seguridad CVEs
```

Se ejecuta puntualmente con `uv run pip-audit` para detectar
vulnerabilidades conocidas en el árbol de dependencias.

### 3.3 Configuración de seguridad de `uv` (cooldown de cadena de suministro)

Añadir a `pyproject.toml`:

```toml
[tool.uv]
exclude-newer = "7 days"
```

**Justificación:** ignora paquetes publicados en los últimos 7 días
para dar tiempo a la comunidad a detectar versiones comprometidas
antes de instalarlas (cf. ataque LiteLLM/Telnyx, marzo 2026, donde
versiones maliciosas fueron retiradas dentro de los primeros días tras
publicación). Es el equivalente Python al `minimumReleaseAge: 1440` de
pnpm en el frontend (ver `spec-frontend.md` §3.1).

## 4. Modelos Pydantic (`models.py`)

### 4.1 Requests

```python
class QueryRequest(BaseModel):
    pregunta: str = Field(..., min_length=1, max_length=5000)

class PlanRepasoRequest(BaseModel):
    tema: str = Field(..., min_length=1, max_length=500)
    fecha_inicio: date
    email: EmailStr | None = None
```

### 4.2 Responses

```python
class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    qdrant_ok: bool
    gemini_ok: bool

class Fuente(BaseModel):
    archivo: str
    chunk_index: int
    score: float
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

class OcrResponse(BaseModel):
    texto: str
    caracteres: int

class DocumentoIndexado(BaseModel):
    nombre_archivo: str
    source_path: str
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
```

## 5. Endpoints

| Método | Ruta                       | Request                     | Response                | Notas |
| ------ | -------------------------- | --------------------------- | ----------------------- | ----- |
| GET    | `/health`                  | —                           | `HealthResponse`        | Verifica Qdrant y Gemini con un ping liviano |
| GET    | `/documentos-indexados`    | —                           | `DocumentosResponse`    | Scroll Qdrant, agrupa por `source_path` |
| POST   | `/upload-document`         | `multipart/form-data`<br>header `X-Filename` | `UploadResponse` | Guarda y re-ingesta |
| POST   | `/query`                   | `QueryRequest`              | `QueryResponse`         |       |
| POST   | `/plan-repaso`             | `PlanRepasoRequest` o multipart con archivo + tema | `PlanRepasoResponse` |       |
| POST   | `/ocr-imagen`              | `multipart/form-data` (campo `file`) | `OcrResponse` | Solo OCR, no indexa |
| POST   | `/ingestar`                | —                           | `{ total_chunks: int }` | Re-indexa toda la carpeta `data/ejemplos` |

### 5.1 Detalles por endpoint

**`POST /upload-document`:**

- Validar extensión contra lista blanca (`.pdf`, `.txt`, `.md`, `.png`,
  `.jpg`, `.jpeg`).
- Validar tamaño máximo: 10 MB para imágenes, 25 MB para PDF.
- Sanitizar nombre de archivo con `utils/safe_filename.py`
  (sin path traversal, sin caracteres especiales).
- Guardar en `data/ejemplos/<safe-name>`.
- Disparar `AgenteExtraccion.ingestar_documento(path)` solo sobre ese
  archivo (no re-indexar todo).
- Devolver número de chunks creados.

**`POST /query`:**

- Llamar a `AgenteRespuesta.responder(pregunta)`.
- Si Qdrant devuelve resultados con score >= umbral (configurable, por
  defecto `0.55` para COSINE en Gemini), usar RAG.
- Si no, generar respuesta sin contexto y marcar `origen="modelo"`.
- Captura excepciones de Qdrant/Gemini y devuelve `503` con mensaje
  claro, no `500` opaco.

**`POST /plan-repaso`:**

- Aceptar dos modos:
  - JSON con `tema` + `fecha_inicio` + `email?`.
  - Multipart con archivo + `tema` + `fecha_inicio` + `email?`.
- En el modo archivo: indexar primero el archivo subido.
- Generar 4 sesiones (D+1, D+7, D+14, D+30).
- Si `email` está presente: hacer POST al webhook de Make.com y
  reflejar `email_enviado=True` solo si Make.com respondió 2xx.

**`POST /ocr-imagen`:**

- Solo extrae texto, NO indexa.
- Si el frontend luego quiere indexar el texto extraído (botón
  "Indexar documento"), llamará a `/upload-document` con un `.txt`
  generado en cliente.

## 6. Agentes

### 6.1 `AgenteExtraccion`

**Responsabilidad:** ingestar documentos a Qdrant.

```python
class AgenteExtraccion:
    def __init__(self, qdrant_client, gemini_service, vision_service): ...

    async def ingestar_documento(self, path: Path) -> int:
        """Ingesta un único documento. Devuelve número de chunks creados."""

    async def ingestar_carpeta(self, carpeta: Path) -> dict[str, int]:
        """Ingesta todos los archivos soportados de una carpeta."""

    # Internos
    async def _extraer_texto(self, path: Path) -> str: ...
    def _chunkear(self, texto: str) -> list[str]: ...
    async def _embed_y_upsert(self, chunks: list[str], source_path: str, tipo: str) -> int: ...
```

Reglas:

- Chunking: `max_chars=900`, `overlap=150`, `max_chunks=100`.
- Embeddings: batch a Gemini (no uno por uno).
- `point_id` actual: usar UUIDv5 determinístico
  (`uuid.uuid5(NAMESPACE, f"{source_path}|{chunk_index}")`).
  Esto resuelve idempotencia (al re-subir, sobrescribe).
- Payload mínimo: `texto`, `source_path`, `nombre_archivo`,
  `tipo_fuente`, `chunk_index`, `embedding_model`, `embedding_dim`,
  `schema_version`, `created_at`.

### 6.2 `AgenteRespuesta`

**Responsabilidad:** responder consultas con RAG.

```python
class AgenteRespuesta:
    def __init__(self, qdrant_client, gemini_service): ...

    async def responder(self, pregunta: str, top_k: int = 5,
                        umbral_score: float = 0.55) -> QueryResponse: ...
```

Reglas:

- Embedding de la pregunta con `gemini-embedding-001`
  (`outputDimensionality=768`, renormalizado a norma unitaria).
- `query_points` sobre Qdrant con `limit=top_k`.
- Filtrar por umbral. Si quedan ≥1 fuentes: RAG. Si no: modelo solo.
- Prompt RAG: incluye los chunks como contexto numerado y la pregunta
  literal del usuario. Instruye al modelo a citar [Fuente N] en su
  respuesta.

### 6.3 `AgentePlanRepaso`

**Responsabilidad:** generar planes de repaso espaciado.

```python
class AgentePlanRepaso:
    def __init__(self, qdrant_client, gemini_service, agente_extraccion,
                 make_webhook): ...

    async def generar_plan(self, tema: str, fecha_inicio: date,
                           email: str | None = None,
                           archivo: Path | None = None) -> PlanRepasoResponse: ...
```

Reglas:

- Si `archivo` se pasa, primero llamar a
  `agente_extraccion.ingestar_documento(archivo)`.
- Buscar contexto en Qdrant relevante al tema.
- Generar las 4 sesiones con prompts diferenciados (D+1 enfatiza
  repaso inicial, D+30 consolidación final).
- Calcular fechas con `fecha_inicio + timedelta(days=N)`.
- Si `email` está, POST a `MAKE_WEBHOOK_URL` con el plan.
- `email_enviado` solo `True` si Make.com respondió 2xx.

## 7. Servicios externos

### 7.1 `services/gemini.py`

Wrapper del SDK `google-genai`. Métodos:

```python
class GeminiService:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Devuelve vectores de 768 dim, renormalizados a norma 1. Llama en batches."""

    async def embed_query(self, text: str) -> list[float]:
        """Igual que embed_texts pero para un único texto."""

    async def generate(self, prompt: str, system: str | None = None) -> str: ...

    @staticmethod
    def _normalize(vec: list[float]) -> list[float]:
        """Renormaliza un vector a norma euclídea 1. Necesario tras truncar
        con outputDimensionality (MRL): los embeddings truncados pierden
        la norma unitaria y degradan COSINE en Qdrant."""
        import math
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
```

Modelos:
- LLM: `gemini-flash-latest`.
- Embeddings: `gemini-embedding-001` (reemplazo GA de `text-embedding-004`,
  deprecado 14-ene-2026). Se llama con
  `outputDimensionality=settings.embedding_output_dimensionality` (768).
  Tras la llamada **es obligatorio aplicar `_normalize()`** a cada vector
  antes de devolverlo o upsertearlo: el truncamiento MRL produce vectores
  con norma ≠ 1 (medido empíricamente: ≈ 0.57), lo que degrada la métrica
  COSINE en Qdrant.

### 7.2 `services/vision.py`

```python
class VisionService:
    async def ocr(self, image_bytes: bytes, mime: str) -> str:
        """DOCUMENT_TEXT_DETECTION. Devuelve fullTextAnnotation.text."""
```

### 7.3 `services/qdrant_client.py`

Wrapper sobre `qdrant-client`. Métodos relevantes:

```python
class QdrantService:
    def ensure_collection(self) -> None:
        """Crea la colección si no existe con 768 dim + COSINE."""

    def upsert_points(self, points: list[PointStruct]) -> None: ...

    def query(self, vector: list[float], limit: int) -> list[ScoredPoint]: ...

    def scroll_all(self, batch: int = 256) -> Iterator[Record]: ...

    def ping(self) -> bool: ...
```

### 7.4 `services/make_webhook.py`

```python
class MakeWebhookService:
    async def enviar_plan(self, payload: dict) -> bool:
        """POST al webhook. True si 2xx."""
```

## 8. Configuración (`settings.py`)

Usar `pydantic-settings` para centralizar todas las variables:

```python
class Settings(BaseSettings):
    gemini_api_key: str
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str = "mentor_ia_aprendizaje"
    google_vision_key_json_path: Path
    make_webhook_url: str | None = None
    base_docs_dir: Path = Path("./data/ejemplos")
    cors_origins: list[str] = ["http://localhost:3000"]
    embedding_model: str = "gemini-embedding-001"
    embedding_output_dimensionality: int = 768
    llm_model: str = "gemini-flash-latest"
    embedding_dim: int = 768
    chunk_max_chars: int = 900
    chunk_overlap: int = 150
    chunk_max: int = 100
    rag_score_threshold: float = 0.55
    rag_top_k: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

## 9. CORS

```python
CORSMiddleware(
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

En desarrollo: `http://localhost:3000`. En producción: solo
`https://mentor-ia-sistema.vercel.app`.

## 10. Logging

Usar `loguru` configurado en `src/logger.py`:

- Formato JSON en producción.
- Formato legible en desarrollo (color + timestamps).
- `request_id` propagado vía middleware en cada request.
- Sin `print()` en ningún archivo del proyecto.

## 11. Manejo de errores

Cada endpoint debe distinguir tres tipos de error:

| Código | Cuándo                                         |
| ------ | ---------------------------------------------- |
| 400    | Input inválido (extensión, tamaño, formato)    |
| 404    | Recurso no encontrado                          |
| 422    | Pydantic validation error (automático)         |
| 503    | Servicio externo caído (Qdrant, Gemini, Vision, Make) |
| 500    | Errores no esperados (excepción no manejada)   |

Cada respuesta de error tiene este formato:

```json
{
  "error": "string corto identificador",
  "message": "explicación human-readable",
  "request_id": "uuid"
}
```

## 12. Dockerfile y docker-compose

### 12.1 `Dockerfile`

```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY src ./src
EXPOSE 8000
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 12.2 `docker-compose.yml`

```yaml
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data/ejemplos:/app/data/ejemplos
      - ./credentials:/app/credentials:ro
    restart: unless-stopped
```

No incluir Qdrant en el compose porque se usa Qdrant Cloud (gestionado).

## 13. Endpoint `/health` profundo

Debe verificar:

1. La app responde.
2. Conexión a Qdrant Cloud (`client.get_collections()`).
3. Conexión a Gemini (`embed_query("ping")` con timeout 2s).

Devuelve `200` con `qdrant_ok` y `gemini_ok` booleanos. No falla con 503
si alguno está caído; informa el estado real para que el frontend pueda
mostrar el badge.

## 14. Lo que NO debe hacer el agente

- Agregar autenticación JWT, login, o sistema de usuarios.
- Agregar OpenAI, Anthropic u otro LLM distinto a Gemini.
- Agregar Celery, Redis o cualquier sistema de colas.
- Modificar parámetros de chunking sin pedir confirmación.
- Cambiar la dimensión del vector (debe quedarse en 768).
- Agregar dependencias pesadas sin justificación
  (Postgres, MongoDB, etc.).

## 15. Criterios de aceptación

El backend está terminado cuando:

- [ ] `docker compose up` arranca sin errores.
- [ ] `GET /health` responde 200 con `qdrant_ok=true` y `gemini_ok=true`.
- [ ] Subir un PDF de 5 páginas devuelve `chunks_ingresados > 0`.
- [ ] Una consulta en `/query` sobre ese PDF devuelve `origen="rag"`
      con al menos una fuente.
- [ ] Generar un plan con email envía efectivamente un correo a la
      dirección indicada (vía Make.com).
- [ ] OCR sobre una imagen con texto devuelve `texto` no vacío.
- [ ] Re-subir el mismo PDF NO duplica chunks (idempotencia con UUIDv5).
- [ ] Todos los logs son estructurados (loguru), sin `print()`.
- [ ] El CORS solo permite los orígenes configurados.

---

_Última actualización: 2026-05-11._
