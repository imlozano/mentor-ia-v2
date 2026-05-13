# Skill — Crear un nuevo agente Python en Mentor IA

Aplicable cuando: hay que añadir una nueva clase `Agente*` al proyecto.

## Reglas

1. Cada agente vive en `backend/src/agentes/agente_<nombre>.py`.
2. Cada agente recibe sus dependencias por constructor (Qdrant,
   Gemini, etc.), NO las crea adentro. Esto facilita tests y mocks.
3. Cada método público debe tener type hints completos y docstring.
4. Logging con `loguru`, NO `print()`.
5. Los métodos asincrónicos (`async def`) son obligatorios para
   métodos que llaman a servicios externos.

## Plantilla base

```python
"""Agente <Nombre>: <responsabilidad en una línea>."""
from __future__ import annotations

from dataclasses import dataclass
from loguru import logger

from ..services.qdrant_client import QdrantService
from ..services.gemini import GeminiService


class Agente<Nombre>:
    """<Descripción de la responsabilidad del agente.>

    Este agente NO se comunica con otros agentes directamente. La
    coordinación la hace el backend (app.py) invocándolos uno por uno.
    """

    def __init__(self, qdrant: QdrantService, gemini: GeminiService) -> None:
        self._qdrant = qdrant
        self._gemini = gemini

    async def metodo_principal(self, input_param: str) -> dict:
        """<Descripción del método.>

        Args:
            input_param: <descripción>.

        Returns:
            <descripción del retorno>.

        Raises:
            <Excepciones que puede lanzar>.
        """
        logger.info("Agente<Nombre>: inicio metodo_principal", input=input_param)
        # implementación
        result = {...}
        logger.info("Agente<Nombre>: fin metodo_principal", result_size=len(result))
        return result
```

## Anti-patrones a evitar

- Crear el cliente Qdrant adentro del agente. Mal:
  ```python
  def __init__(self):
      self._qdrant = QdrantClient(url=os.environ["QDRANT_URL"])  # MAL
  ```
  El cliente debe inyectarse.

- Comunicación directa entre agentes. Mal:
  ```python
  class AgenteRespuesta:
      def __init__(self, agente_extraccion):  # MAL
          ...
  ```
  Si dos agentes necesitan coordinarse, lo hace `app.py`, no se
  acoplan entre sí. (Excepción documentada: `AgentePlanRepaso` puede
  invocar a `AgenteExtraccion` cuando el usuario sube un archivo para
  generar un plan.)

- Capturar todas las excepciones con `except Exception`. Mal:
  ```python
  try:
      ...
  except Exception:  # MAL: oculta bugs reales
      return None
  ```
  Capturar excepciones específicas y dejar que las inesperadas suban.

## Después de crear el agente

1. Instanciarlo en `src/deps.py` con sus dependencias.
2. Inyectarlo en los endpoints que lo usen vía `Depends()`.
3. Documentar en `docs/academic/Arquitectura_Multiagente.md` si la
   responsabilidad amerita un cuarto agente (avisar primero al
   estudiante).
