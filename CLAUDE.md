---
description: 
alwaysApply: true
---

# CLAUDE.md — Instrucciones para agentes de IA en este repositorio

Este archivo lo lee Claude Code (o cualquier otro agente) cada vez que se
abre el repositorio. Define el contexto del proyecto, las reglas
inmutables y dónde encontrar la información detallada.

---

## 1. Contexto del proyecto

**Mentor IA** es un sistema multiagente de aprendizaje con RAG. Es un
**prototipo académico funcional**, NO un producto comercial.

- Asignatura: Administración de Proyectos de Software.
- Universidad: Tecnológica de Pereira (UTP).
- Estudiante: Miguel Alejandro Lozano Trejos (desarrollador único).
- Entrega final: 20 de mayo de 2026.

## 2. Reglas inmutables del proyecto

Estas reglas NO se discuten ni se renegocian. Si una instrucción del
usuario las contradice, el agente debe preguntar antes de proceder.

### 2.1 Alcance — qué es y qué NO es

- ✅ Es un prototipo académico funcional para un único usuario.
- ❌ NO es un SaaS multitenant.
- ❌ NO tiene autenticación, login, ni cuentas de usuario.
- ❌ NO es un producto comercial.
- ❌ NO se integra con LMS (Moodle, Canvas).
- ❌ NO usa OpenAI; usa Google Gemini.

### 2.2 Stack obligatorio

| Capa            | Tecnología obligatoria                                  |
| --------------- | ------------------------------------------------------- |
| Frontend        | Next.js 16 (App Router) + React 19 + TypeScript 5       |
| Gestor de paquetes frontend | pnpm 11+ con `minimumReleaseAge: 1440` (cooldown 24 h) y `blockExoticSubdeps: true` (defensa de cadena de suministro: Shai-Hulud 2.0 / Axios compromise) |
| Node.js         | 22+                                                     |
| Estilos         | Tailwind CSS 4 + shadcn/ui sobre Radix Primitives       |
| Backend         | FastAPI + Python 3.11+                                  |
| Base vectorial  | Qdrant Cloud, colección `mentor_ia_aprendizaje`, 768 dim, COSINE |
| Embeddings      | OpenAI `text-embedding-3-large` con `dimensions=768` (MRL nativo, vectores renormalizados) — migrado desde Gemini el 2026-05-17 por agotamiento repetido de cuota free; ver §2.5 |
| LLM             | OpenAI `gpt-4o-mini` (chat completions). Decisión documentada en §2.5. |
| OCR             | OpenAI `gpt-4o-mini` (Vision multimodal sobre chat completions). Decisión documentada en §2.5. |
| Email           | Make.com Custom Webhook + Gmail Sender                  |
| PDF             | `pypdf` 6.x (NO PyPDF2, que está deprecated)            |

### 2.3 Parámetros técnicos fijos

- Chunking: `max_chars=900`, `overlap=150`, `max_chunks=100`.
- Vector: 768 dimensiones, distancia COSINE.
- Plan de repaso: 4 sesiones (D+1, D+7, D+14, D+30).
- Tipos de fuente soportados: PDF, TXT, MD, PNG, JPG, JPEG.

### 2.4 Decisiones técnicas con justificación

Si el agente quiere proponer cambiar Qdrant por otra base vectorial,
Gemini por otro LLM, o cualquier elemento del stack, debe **preguntar
explícitamente**. Estas decisiones están justificadas en
[`docs/academic/Documento_Tecnico.md`](./docs/academic/Documento_Tecnico.md),
sección 6.

### 2.5 Migración LLM y OCR a OpenAI (aplicada 2026-05-15)

Motivación: el tier gratuito de Gemini 3 Flash quedó en 20 requests/día
por modelo (cuota agotada durante las pruebas E2E pre-despliegue del
2026-05-15). El fallback local del agente de plan-repaso generaba
descripciones genéricas inservibles para defensa académica.

Decisión: migrar todo el uso de LLM y OCR multimodal a
OpenAI `gpt-4o-mini`. Embeddings permanecen en Gemini
(`gemini-embedding-001`, cuota RPD 1000 suficiente y modelo ya
calibrado en 768d MRL para Qdrant COSINE).

Aplicado en commit `<pendiente>` (sesión 2026-05-15):

- Servicio nuevo `src/services/openai_service.py` con `generate`,
  `extract_text_from_image`, `extract_text_from_pdf_page`, `ping`,
  `close`. Reintentos con backoff frente a `RateLimitError`/`APITimeoutError`.
- `AgenteRespuesta`, `AgentePlanRepaso`, `AgenteExtraccion` inyectan
  `OpenAIService` y usan sus métodos en lugar de Gemini.
- `GeminiService` queda solo con `embed_query/embed_texts/ping` (el
  método `generate` se eliminó).
- `src/services/gemini_vision.py` eliminado.
- `Settings` añade `openai_api_key`, `openai_chat_model`,
  `openai_vision_model` (defaults `gpt-4o-mini`).
- `/health` ahora pingea Qdrant + Gemini (embeddings) + OpenAI (chat+vision).
- Dependencia `openai>=1.50,<2.0` en `pyproject.toml`.

Para defender en sustentación: la cuota Gemini-Flash tier gratuito
era incompatible con un sistema multiagente con varias llamadas LLM
por petición; gpt-4o-mini con créditos pagados ofrece RPM/TPM
adecuados y precio bajo (~USD 0.15/1M input tokens). Mantener Gemini
para embeddings preserva la inversión de ingeniería en MRL/COSINE.

**Adenda 2026-05-15 (mismo día):** `gemini-embedding-001` también
agotó cuota free (1000 RPD) durante la validación E2E. Migrado a
`gemini-embedding-2` (modelo nuevo con bucket de cuota separado;
mismo MRL→768 + renormalización). Esto requirió **borrar la colección
Qdrant y re-indexar** los smoke docs (vectores 001 y 2 no son
semánticamente comparables).

**Adenda 2026-05-17 (plan B activado):** `gemini-embedding-2` agotó
cuota free 1000 RPD durante el despliegue a producción (DigitalOcean
+ Vercel). El healthcheck cada 30s + uso real consumió cuota en horas.
Migración completa a OpenAI:

- `OpenAIService.embed_query/embed_texts` con `text-embedding-3-large`
  + parámetro `dimensions=768` (MRL nativo) + renormalización.
- `GeminiService` eliminado por completo; `google-genai` removido de
  `pyproject.toml`; `GEMINI_API_KEY` ya no se requiere.
- `/health` ahora solo pingea Qdrant + OpenAI (sin `gemini_ok`).
- Nueva ronda de **borrado de colección Qdrant + re-indexación** porque
  los vectores de `gemini-embedding-2` y `text-embedding-3-large` no son
  semánticamente comparables.
- `Settings` añade `openai_embedding_model`, `openai_embedding_dimensions`.

Para defender en sustentación: el tier gratuito de Gemini embeddings
(1000 RPD) era incompatible con la frecuencia de healthchecks (cada
30s × 2880 al día) + el uso real de RAG/plan/upload. OpenAI con
créditos paga ofrece límites por minuto/día holgados para el alcance
académico. Coste estimado: ~USD 0.13 por 1M tokens, despreciable.

## 3. Estructura del repositorio

```
mentor-ia-v2/
├── CLAUDE.md                  ← este archivo (instrucciones globales)
├── .claude/skills/            ← skills personalizadas
├── docs/
│   ├── academic/              ← documentos académicos (NO modificar sin pedir)
│   └── specs/                 ← specs técnicas que leen los agentes
├── backend/                   ← FastAPI (construir según spec-backend.md)
├── frontend/                  ← Next.js (construir según spec-frontend.md)
└── README.md
```

## 4. Cómo trabajar en este repo

### 4.1 Orden de lectura para construir

1. Este `CLAUDE.md`.
2. [`docs/specs/implementation-plan.md`](./docs/specs/implementation-plan.md)
   — el orden cronológico de tareas.
3. Para tareas de backend: [`docs/specs/spec-backend.md`](./docs/specs/spec-backend.md).
4. Para tareas de frontend: [`docs/specs/spec-frontend.md`](./docs/specs/spec-frontend.md).
5. Si hay ambigüedad sobre arquitectura: [`docs/academic/Arquitectura_Multiagente.md`](./docs/academic/Arquitectura_Multiagente.md).
6. Si hay ambigüedad sobre datos: [`docs/academic/Modelo_Datos_Qdrant.md`](./docs/academic/Modelo_Datos_Qdrant.md).
7. Si hay ambigüedad sobre flujos: [`docs/academic/Flujo_Interaccion_Usuario_Sistema.md`](./docs/academic/Flujo_Interaccion_Usuario_Sistema.md).
8. Si hay ambigüedad sobre UI: [`docs/academic/wireframes-frontend.md`](./docs/academic/wireframes-frontend.md).

### 4.2 Reglas de modificación de archivos

| Carpeta o archivo        | ¿Puedo modificar?                                       |
| ------------------------ | ------------------------------------------------------- |
| `docs/academic/*`        | NO sin pedir confirmación al usuario.                   |
| `docs/specs/*`           | SÍ, si descubres inconsistencias o mejoras, pero avisa. |
| `backend/`               | SÍ, siguiendo `spec-backend.md`.                        |
| `frontend/`              | SÍ, siguiendo `spec-frontend.md`.                       |
| `CLAUDE.md`              | NO sin pedir confirmación al usuario.                   |
| `README.md`              | SÍ, mantenerlo actualizado.                             |
| `.gitignore`             | SÍ, ampliarlo si encuentras patrones que faltan.        |

### 4.3 Convenciones de código

**Backend (Python):**

- Type hints en todas las funciones públicas.
- Pydantic para validar entradas y salidas.
- `loguru` para logging (no `print()`).
- `httpx` para llamadas HTTP externas (no `requests`).
- Estructura: `src/app.py` (endpoints), `src/agentes/` (3 agentes),
  `src/services/` (clientes a Gemini, Gemini Vision, Make; futuro OpenAI), `src/models.py`
  (Pydantic schemas).
- Variables de entorno: leer con `pydantic-settings` desde un `Settings`
  centralizado, NO con `os.environ.get` esparcido.

**Frontend (TypeScript):**

- `strict: true` en `tsconfig.json`.
- Componentes en `components/` (kebab-case en nombres de archivo,
  PascalCase en componentes).
- Tipos compartidos en `lib/types.ts`.
- Cliente API en `lib/api.ts`.
- shadcn/ui en `components/ui/`.
- Tailwind 4 con variables CSS para tokens.

### 4.4 Reglas de comunicación con el usuario

- Si una decisión técnica tiene más de una opción razonable, **proponer
  2-3 opciones y dejar que el usuario elija**, no decidir solo.
- Si una instrucción contradice las reglas inmutables (sección 2),
  **detenerse y preguntar**.
- Si una tarea es ambigua, **pedir clarificación antes de codificar**,
  no asumir.
- Antes de escribir código, **listar los archivos que se van a crear o
  modificar** y pedir confirmación si son más de 3.

### 4.5 Reglas de testing

- Para el alcance del proyecto académico no se exigen tests unitarios
  ni de integración formales.
- Si se añaden, deben ir en `backend/tests/` con `pytest` y `httpx`
  asíncrono para los endpoints.
- Los smoke tests manuales (subir un PDF de prueba, hacer una consulta,
  generar un plan) deben quedar documentados en
  `docs/specs/smoke-tests.md` cuando se cree.

## 5. Variables de entorno requeridas

El agente NO debe hardcodear claves ni URLs. Todas las variables están
en `.env.example` (que se crea como plantilla) y se leen en código vía
`Settings`.

**Backend (`backend/.env`):**

```
OPENAI_API_KEY=...
QDRANT_URL=...
QDRANT_API_KEY=...
QDRANT_COLLECTION=mentor_ia_aprendizaje
MAKE_WEBHOOK_URL=...
BASE_DOCS_DIR=./data/ejemplos
CORS_ORIGINS=["https://www.iamentor.tech","https://iamentor.tech","http://localhost:3000"]
```

Notas:
- `CORS_ORIGINS` debe ir como **JSON array** (con corchetes y comillas dobles),
  no CSV. `pydantic-settings` 2.x intenta `json.loads()` antes de los validators.
- `GEMINI_API_KEY` y `GOOGLE_VISION_KEY_JSON_PATH` quedaron obsoletos tras
  la migración total a OpenAI (§2.5). Pueden eliminarse del repo y del Droplet.

**Frontend (`frontend/.env.local`):**

```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

## 6. Despliegue previsto

| Componente | Plataforma                              |
| ---------- | --------------------------------------- |
| Frontend   | Vercel                                  |
| Backend    | DigitalOcean Droplet con Docker Compose |

El backend debe poder correr en local con `docker compose up` y en DO
con el mismo `docker-compose.yml`.

## 7. Skills personalizadas

En `.claude/skills/` hay skills específicas para tareas comunes en
este repo. El agente debe consultarlas cuando aplique:

- `frontend-shadcn-setup.md` — cómo añadir componentes shadcn.
- `agent-creation.md` — patrón para crear un nuevo agente Python.
- `endpoint-creation.md` — patrón para añadir un endpoint FastAPI.

(Las skills se irán creando conforme se necesiten. Si una skill
relevante no existe, el agente puede proponer crearla.)

## 8. Para defender en sustentación

El estudiante debe poder explicar cualquier decisión de este repo. Por
eso:

- Cada archivo `.md` académico tiene una sección final *"Para defender
  en sustentación"* con 3-4 puntos clave.
- Cualquier cambio en el código debe poder justificarse técnicamente
  ante la profesora.
- El agente NO debe introducir librerías o patrones "porque están de
  moda" sin justificación técnica.

### 8.1 Heurística RAG vs modelo (cómo demo-ar en vivo)

El backend usa un **umbral de similitud coseno = 0.55** (`RAG_SCORE_THRESHOLD`).
Si ningún chunk supera ese score, cae al **modelo base** sin inventar
fuentes. Es comportamiento correcto; hay que saber demostrarlo.

| Tipo de pregunta                                         | Resultado esperado                                          |
| -------------------------------------------------------- | ----------------------------------------------------------- |
| *"¿Qué dice el archivo X.pdf?"* / *"Explícame el archivo X"* | `origen: modelo` — la query es meta-archivo, no contenido.  |
| *"¿Qué es la atención multi-cabeza?"* / *"¿Cómo funciona X concepto del paper?"* | `origen: rag` con `[Fuente N]` citada y score > 0.55. |

Lo que decir en sustentación: *"El sistema solo cita fuentes cuando
el embedding de la pregunta matchea con el de algún chunk indexado
sobre umbral 0.55. Si la pregunta es meta (nombra el archivo en vez
de preguntar por su contenido), el embedding no acerca chunks
técnicos del documento, y el sistema cae al modelo base con badge
claro. Es una salvaguarda contra alucinación de fuentes."*

Para demo: tener preparadas 2 preguntas — una de cada tipo — sobre
el mismo documento indexado, y mostrar los badges distintos.

## 9. Seguimiento del proyecto y ClickUp

El avance real del proyecto se registra en ClickUp como herramienta
única de seguimiento, alineado al WBS de la sección 6 del documento
académico. No hay otra fuente de verdad (no se usan issues de GitHub
ni tableros adicionales).

- **Espacio:** *Mentor IA – Sistema de Aprendizaje Inteligente*
- **List ID:** `901712277205`

### 9.1 Flujo de estados de subtareas

Cada subtarea ClickUp asociada a una fase del
[`docs/specs/implementation-plan.md`](./docs/specs/implementation-plan.md)
recorre tres estados, gestionados por el agente:

1. `pendiente` — estado inicial.
2. `en curso` — el agente la mueve aquí **al empezar** la fase.
3. `completado` — el agente la mueve aquí **al cerrar** la fase, una
   vez que el usuario confirma que el criterio de aceptación se cumple,
   y añade un comentario con formato:
   `Completado en commit <sha> — <breve descripción>`.

### 9.2 Reglas de uso

- **No crear nuevas tareas en ClickUp sin permiso explícito del usuario.**
  Solo modificar las que ya existen.
- Si una fase del implementation plan no tiene subtarea correspondiente
  (Fase 0, 3, 8, 11, 12, 13), no forzar asociación: dejar constancia
  en el mensaje de commit.
- Antes de la primera mutación en ClickUp dentro de una sesión, el
  agente avisa explícitamente al usuario. Tras el OK inicial, no
  vuelve a preguntar para cada cambio de estado dentro de la misma
  sesión: aplica el flujo de 3 estados automáticamente.

### 9.3 Mapeo WBS ↔ Tarea padre ClickUp

| Fase del WBS                          | Tarea padre   | Estado     |
| ------------------------------------- | ------------- | ---------- |
| 1. Inicio y Planificación             | `86e0j1nzq`   | Completada |
| 2. Diseño del Sistema                 | `86e0j1nrp`   | Completada |
| 3. Desarrollo del Backend             | `86e0j1ntn`   | En curso   |
| 4. Desarrollo del Frontend            | `86e0j1ntr`   | En curso   |
| 5. Integración y Automatización       | `86e0j1ntx`   | En curso   |
| 6. Pruebas                            | `86e0j1ntz`   | En curso   |
| 7. Documentación y Cierre             | `86e0j1nv4`   | En curso   |

### 9.4 Mapeo Fase del implementation plan ↔ Subtarea ClickUp

| Fase del plan                | Subtarea(s) ClickUp                                                |
| ---------------------------- | ------------------------------------------------------------------ |
| Fase 1 (scaffolding backend) | `86e0j1p1r` Implementación de la API REST con FastAPI              |
| Fase 2 (servicios externos)  | `86e0j1p29` Integración del agente con Google Gemini (se cierra al terminar Fase 2) |
| Fase 3 (utilidades)          | (sin subtarea directa; vincular al commit)                         |
| Fase 4 (AgenteExtraccion)    | `86e0j1p1t` Módulo de indexación de documentos (PDF, TXT, Markdown) |
| Fase 5 (AgenteRespuesta)     | `86e0j1p1v` Módulo de búsqueda semántica con RAG                   |
| Fase 6 (AgentePlanRepaso)    | `86e0j1p2d` Generación de planes de estudio + `86e0j1p2j` Envío automatizado de planes por correo |
| Fase 7 (OCR)                 | `86e0j1p1y` Módulo de OCR para extracción de texto desde imágenes  |
| Fase 8 (scaffolding frontend)| (sin subtarea directa)                                             |
| Fase 9 (StudyAssistant)      | `86e0j1p22` Interfaz de carga y gestión de documentos + `86e0j1p24` Interfaz del chat inteligente |
| Fase 10 (ReviewPlan)         | `86e0j1p26` Módulo de visualización de planes de estudio           |
| Fase 11 (StatusIndicator)    | (sin subtarea directa)                                             |
| Fase 12 (despliegue backend) | (sin subtarea directa)                                             |
| Fase 13 (despliegue frontend)| (sin subtarea directa)                                             |
| Fase 14 (smoke tests finales)| `86e0j1p35` Pruebas de precisión RAG + `86e0j1p38` Pruebas de rendimiento OCR |

---

_Última actualización: 2026-05-11._
