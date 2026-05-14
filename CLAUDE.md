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
| Estilos         | Tailwind CSS 4 + shadcn/ui sobre Radix Primitives       |
| Backend         | FastAPI + Python 3.11+                                  |
| Base vectorial  | Qdrant Cloud, colección `mentor_ia_aprendizaje`, 768 dim, COSINE |
| Embeddings      | Google Gemini `gemini-embedding-001` con `outputDimensionality=768` (MRL, vectores renormalizados) |
| LLM             | Google Gemini `gemini-flash-latest`                     |
| OCR             | Google Cloud Vision `DOCUMENT_TEXT_DETECTION`           |
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
  `src/services/` (clientes a Gemini, Vision, Make), `src/models.py`
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
GEMINI_API_KEY=...
QDRANT_URL=...
QDRANT_API_KEY=...
QDRANT_COLLECTION=mentor_ia_aprendizaje
GOOGLE_VISION_KEY_JSON_PATH=./credentials/vision.json
MAKE_WEBHOOK_URL=...
BASE_DOCS_DIR=./data/ejemplos
CORS_ORIGINS=http://localhost:3000,https://mentor-ia-sistema.vercel.app
```

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

---

_Última actualización: 2026-05-11._
