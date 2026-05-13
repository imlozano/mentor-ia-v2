# Skill — Crear un nuevo endpoint FastAPI en Mentor IA

Aplicable cuando: hay que añadir un nuevo endpoint a `src/app.py`.

## Reglas

1. Cada endpoint usa modelos Pydantic para request y response.
2. Cada endpoint declara su `response_model` explícitamente.
3. Las dependencias (agentes, servicios) se inyectan con `Depends()`.
4. El logging se hace al principio y al final del endpoint, no en
   pasos intermedios.
5. Captura de errores: NO usar `try/except` opaco; dejar que
   FastAPI maneje los `HTTPException` y los `Pydantic ValidationError`.

## Plantilla base

```python
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from .models import MiRequest, MiResponse
from .deps import get_agente_x


@app.post(
    "/mi-endpoint",
    response_model=MiResponse,
    status_code=status.HTTP_200_OK,
    summary="Descripción corta del endpoint",
    tags=["categoría"],
)
async def mi_endpoint(
    payload: MiRequest,
    agente: AgenteX = Depends(get_agente_x),
) -> MiResponse:
    """Descripción larga del endpoint.

    Devuelve <X>. Puede lanzar:
    - 400 si <validación de negocio>.
    - 503 si <servicio externo caído>.
    """
    logger.info("/mi-endpoint: inicio", payload=payload.model_dump())
    try:
        resultado = await agente.hacer_algo(payload.campo)
    except QdrantServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "qdrant_unavailable", "message": str(e)},
        )
    logger.info("/mi-endpoint: fin", items=len(resultado))
    return MiResponse(...)
```

## Códigos HTTP recomendados

| Caso                                    | Código |
| --------------------------------------- | ------ |
| Operación exitosa                       | 200    |
| Recurso creado                          | 201    |
| Sin contenido (DELETE)                  | 204    |
| Input inválido (negocio)                | 400    |
| Pydantic validation error               | 422 (automático) |
| No autorizado                           | 401    |
| No encontrado                           | 404    |
| Servicio externo caído                  | 503    |
| Bug inesperado                          | 500    |

## Anti-patrones

- Endpoints sin `response_model`:
  ```python
  @app.post("/x")  # MAL: no se valida la salida
  async def x(): ...
  ```

- Capturar `Exception` genérico:
  ```python
  try:
      ...
  except Exception as e:  # MAL: oculta bugs
      raise HTTPException(500, detail=str(e))
  ```
  Captura excepciones específicas.

- Acceso directo a settings dentro del endpoint:
  ```python
  @app.post("/x")
  async def x():
      url = os.environ["QDRANT_URL"]  # MAL
  ```
  La configuración se accede vía `Depends(get_settings)`.

## Después de crear el endpoint

1. Probar con curl o httpie:
   ```bash
   curl -X POST http://localhost:8000/mi-endpoint \
        -H "Content-Type: application/json" \
        -d '{"campo": "valor"}'
   ```
2. Verificar que aparece en `/docs` (OpenAPI auto-generado).
3. Si el endpoint es público, actualizar el frontend cliente en
   `frontend/lib/api.ts` y los tipos en `frontend/lib/types.ts`.
4. Actualizar `docs/academic/Flujo_Interaccion_Usuario_Sistema.md`
   sección 3.1 (Mapa de endpoints) si es un endpoint nuevo
   permanente.
