# Mentor IA — v2

> Sistema multiagente de aprendizaje con RAG sobre documentos propios,
> OCR de imágenes y planes de repaso espaciado por correo.
>
> Proyecto académico de la asignatura **Administración de Proyectos de
> Software** — Tecnología en Desarrollo de Software, Universidad
> Tecnológica de Pereira.

Frontend desplegado: <https://mentor-ia-sistema.vercel.app/>

---

## Estructura del repositorio

```
mentor-ia-v2/
├── CLAUDE.md                  Instrucciones globales para agentes de IA
├── .claude/
│   └── skills/                Skills personalizadas para Claude Code
├── docs/
│   ├── academic/              Documentación entregable a la profesora
│   │   ├── Documento_Tecnico.md
│   │   ├── Arquitectura_Multiagente.md
│   │   ├── Modelo_Datos_Qdrant.md
│   │   ├── Flujo_Interaccion_Usuario_Sistema.md
│   │   ├── wireframes-frontend.md
│   │   └── wireframes/        Imágenes PNG de wireframes
│   └── specs/                 Specs técnicas que consumen los agentes
│       ├── spec-backend.md
│       ├── spec-frontend.md
│       └── implementation-plan.md
├── backend/                   FastAPI + Python (a construir)
├── frontend/                  Next.js 16 + React 19 (a construir)
└── README.md                  Este archivo
```

## Para qué sirve cada carpeta

- **`docs/academic/`** — Documentos que lee la profesora para evaluar.
  No los modifica el agente sin permiso explícito.
- **`docs/specs/`** — Documentos que lee el agente (Claude Code,
  Cursor) para construir el código. Cada spec describe qué hay que
  construir, dónde y bajo qué reglas.
- **`backend/`** — Código del backend FastAPI. El agente lo construye
  siguiendo `docs/specs/spec-backend.md`.
- **`frontend/`** — Código del frontend Next.js. El agente lo construye
  siguiendo `docs/specs/spec-frontend.md`.

## Flujo de trabajo con el agente

1. El estudiante abre Claude Code (o Cursor) en este repo.
2. El agente lee primero `CLAUDE.md` (instrucciones globales).
3. Para construir el backend, lee `docs/specs/spec-backend.md`.
4. Para construir el frontend, lee `docs/specs/spec-frontend.md`.
5. El plan de orden de implementación está en
   `docs/specs/implementation-plan.md`.

## Despliegue previsto

| Componente | Plataforma                                    |
| ---------- | --------------------------------------------- |
| Frontend   | Vercel (gratis)                               |
| Backend    | DigitalOcean Droplet con Docker Compose       |
| Vectorial  | Qdrant Cloud (tier gratuito 1 GB)             |
| LLM/Embeddings | Google Gemini (`gemini-flash-latest`, `text-embedding-004`) |
| OCR        | Google Cloud Vision (`DOCUMENT_TEXT_DETECTION`) |
| Email      | Make.com Custom Webhook + Gmail Sender        |

## Lectura recomendada según rol

- **Profesora evaluadora:** empezar por `docs/academic/Documento_Tecnico.md`.
- **Desarrollador o agente que construye el sistema:** empezar por
  `CLAUDE.md`, luego `docs/specs/implementation-plan.md`.
- **Estudiante revisando el proyecto en sustentación:** la sección
  *"Para defender en sustentación"* al final de cada `.md` académico.
