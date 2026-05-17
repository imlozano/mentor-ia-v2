# Mentor IA

Sistema multiagente de aprendizaje con **RAG** sobre documentos propios,
**OCR** multimodal e **inteligencia generativa** para planes de repaso
espaciado con notificación por correo.

🌐 **Demo en vivo:** <https://www.iamentor.tech>

---

## Características

- 💬 Chat con citación de fuentes (RAG) sobre tus PDF, TXT, Markdown e imágenes.
- 📄 OCR multimodal para PDF escaneados y capturas de imagen.
- 📅 Planes de repaso espaciado generados automáticamente (D+1 · D+7 · D+14 · D+30).
- ✉️ Envío opcional del plan al correo del usuario.
- 🟢 Healthcheck público y degradación visible cuando un servicio cae.

## Stack

| Capa                 | Tecnología                                                    |
| -------------------- | ------------------------------------------------------------- |
| Frontend             | Next.js 16 · React 19 · TypeScript 5 · Tailwind CSS 4 · shadcn/ui |
| Backend              | FastAPI · Python 3.11 · `uv` · Docker Compose                 |
| Base vectorial       | Qdrant Cloud · 768 dims · distancia COSINE                    |
| Embeddings           | OpenAI `text-embedding-3-large` (768d con MRL + renormalización) |
| LLM (chat + plan)    | OpenAI `gpt-4o-mini`                                          |
| OCR                  | OpenAI `gpt-4o-mini` Vision (multimodal)                      |
| Correo               | Make.com Custom Webhook → Gmail Sender                        |
| Hosting backend      | DigitalOcean Droplet + nginx + Let's Encrypt                  |
| Hosting frontend     | Vercel                                                        |

## Arquitectura

```
[ Browser ] ─HTTPS─▶ [ Vercel: Next.js ] ─HTTPS─▶ [ DO Droplet: nginx → FastAPI ]
                                                          ├─▶ Qdrant Cloud (vectores)
                                                          ├─▶ OpenAI (chat / vision / embeddings)
                                                          └─▶ Make.com webhook (email)
```

Tres agentes lógicos en el backend:

- **AgenteExtraccion** — Ingesta, chunking y embeddings hacia Qdrant.
- **AgenteRespuesta** — Búsqueda semántica + síntesis con LLM (RAG).
- **AgentePlanRepaso** — Genera 4 sesiones espaciadas y opcionalmente las envía por correo.

## Estructura del repositorio

```
mentor-ia-v2/
├── backend/      Servicio FastAPI (Python 3.11 + uv + Docker)
├── frontend/     Aplicación Next.js 16 (App Router, Turbopack)
├── docs/         Especificaciones técnicas y documentación de diseño
└── README.md
```

## Ejecución local

**Backend**

```bash
cd backend
cp .env.example .env   # rellenar OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY, MAKE_WEBHOOK_URL
docker compose up -d --build
curl http://localhost:8000/health
```

**Frontend**

```bash
cd frontend
pnpm install
cp .env.local.example .env.local   # NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
pnpm dev
```

Aplicación en <http://localhost:3000>.

## Variables de entorno

Plantilla completa en [`backend/.env.example`](backend/.env.example).
Mínimo viable:

```env
OPENAI_API_KEY=sk-...
QDRANT_URL=https://....cloud.qdrant.io
QDRANT_API_KEY=...
QDRANT_COLLECTION=mentor_ia_aprendizaje
MAKE_WEBHOOK_URL=https://hook.eu2.make.com/...
CORS_ORIGINS=["https://www.tu-dominio.com","http://localhost:3000"]
```

## Despliegue

- **Backend:** Docker Compose en un Droplet Ubuntu 24.04, expuesto por nginx con TLS automático (Let's Encrypt).
- **Frontend:** Vercel, Root Directory `frontend/`, build automático desde `main`.

## Documentación

- [`docs/specs/`](docs/specs/) — Especificaciones técnicas, plan de implementación, política de seguridad de dependencias.
- [`docs/academic/`](docs/academic/) — Documento técnico, modelo de datos, arquitectura multiagente, wireframes.

## Contexto

Trabajo final de la asignatura *Administración de Proyectos de Software* — Tecnología en Desarrollo de Software, Universidad Tecnológica de Pereira (UTP).

## Licencia

Uso académico — UTP.
