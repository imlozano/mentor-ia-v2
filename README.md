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
# Opcional: regex para orígenes dinámicos (p. ej. previews de Vercel)
CORS_ORIGIN_REGEX=^https://mentor-ia-v2-[a-z0-9]+-<scope>\.vercel\.app$
```

## Despliegue

- **Backend:** Docker Compose en un Droplet Ubuntu 24.04, expuesto por nginx con TLS automático (Let's Encrypt).
- **Frontend:** Vercel, Root Directory `frontend/`, build automático desde `main`.

Ambos despliegues son automáticos: cada push a `main` actualiza producción
sin intervención manual. El detalle del pipeline está abajo.

## CI/CD

El repositorio implementa un pipeline completo en GitHub Actions: valida
cada cambio antes de integrarlo y despliega el backend de forma automática
con rollback ante fallo. La rama `main` está protegida — ningún cambio
entra sin pasar las cuatro puertas de calidad.

### Flujo general

```
Pull Request ─▶ 4 quality gates ─▶ merge a main ─▶ deploy automático
                (bloquean el merge)                 (con rollback)
```

### Workflows

| Workflow | Archivo | Dispara en | Función |
| -------- | ------- | ---------- | ------- |
| **CI** | `.github/workflows/ci.yml` | PR y push a `main` | Lint, audit, build y scan de imagen |
| **CodeQL** | `.github/workflows/codeql.yml` | PR, push a `main` y cron semanal | Análisis estático de seguridad (SAST) |
| **Deploy backend** | `.github/workflows/deploy-backend.yml` | push a `main` que toque `backend/` | Despliegue SSH al Droplet con health check y rollback |

### Puertas de calidad (gates)

Un PR no puede mergearse hasta que las cuatro pasen en verde:

1. **`Backend (lint + audit + smoke)`** — `ruff` (lint + formato), `pip-audit`
   (CVEs en dependencias de runtime) y un *smoke import* que verifica que la
   app FastAPI carga sin errores.
2. **`Backend (docker build + Trivy scan)`** — construye la imagen Docker
   (valida el `Dockerfile`) y la escanea con **Trivy**; falla ante cualquier
   CVE `HIGH`/`CRITICAL` con parche disponible. Los hallazgos se publican en
   la pestaña *Security* del repositorio (formato SARIF).
3. **`Frontend (lint + typecheck + audit)`** — `eslint`, `tsc --noEmit` y
   `pnpm audit`.
4. **`Analyze (python)` / `Analyze (javascript-typescript)`** — CodeQL con el
   preset `security-extended`: detecta patrones inseguros en el código
   (inyección, path traversal, credenciales hardcodeadas, etc.).

`pip-audit` y Trivy son complementarios: el primero audita las dependencias
Python del entorno virtual; el segundo escanea la imagen completa, incluyendo
paquetes del sistema operativo del base image.

### Despliegue del backend con rollback

Al integrar un cambio en `backend/`, el workflow de deploy:

1. Se conecta por SSH al Droplet con una clave dedicada (validada con
   `ssh-keygen -y` antes de usarla).
2. Sincroniza el código (`git reset --hard` al commit integrado) y
   reconstruye el contenedor (`docker compose up -d --build`).
3. Ejecuta un **health check** contra `/health` (12 intentos × 5 s).
4. Si responde `200`, registra el commit como *último estable* en el Droplet.
5. Si **no** responde, ejecuta un **rollback automático**: revierte al último
   commit estable, reconstruye y vuelve a verificar. El servicio queda
   restaurado sin intervención manual y el workflow se marca en rojo para
   dejar constancia en el historial.

### Decisiones de seguridad del pipeline

- **Actions ancladas por SHA**, no por tag móvil — evita que una versión
  comprometida de una action de terceros entre de forma silenciosa.
- **Sin `pull_request_target`** — solo se usan `pull_request`, `push` y
  `workflow_dispatch`, de modo que el código de un PR nunca se ejecuta con
  acceso a los secretos del repositorio.
- **`GITHUB_TOKEN` con permisos mínimos** (`contents: read`, y
  `security-events: write` solo donde se suben informes SARIF).
- **Clave SSH de despliegue dedicada**, sin passphrase, eliminada del runner
  al terminar cada ejecución (`shred`).

## Documentación

- [`docs/specs/`](docs/specs/) — Especificaciones técnicas, plan de implementación, política de seguridad de dependencias.
- [`docs/academic/`](docs/academic/) — Documento técnico, modelo de datos, arquitectura multiagente, wireframes.

## Contexto

Trabajo final de la asignatura *Administración de Proyectos de Software* — Tecnología en Desarrollo de Software, Universidad Tecnológica de Pereira (UTP).

## Licencia

Uso académico — UTP.
