# Plan de implementación — Mentor IA v2

> Orden cronológico de tareas para construir el sistema desde cero
> usando agentes de IA (Claude Code, Cursor). El agente debe seguir este
> orden y NO saltarse fases sin avisar.

---

## Fase 0 — Verificación previa (antes de tocar código)

Antes de empezar, el agente confirma con el estudiante que tiene:

- [ ] `GEMINI_API_KEY` con acceso a `gemini-flash-latest` y
      `gemini-embedding-001` (verificar con `outputDimensionality=768`).
- [ ] Cuenta en Qdrant Cloud con cluster activo. Variables `QDRANT_URL`
      y `QDRANT_API_KEY` listas.
- [ ] Credenciales JSON de Google Cloud Vision API descargadas.
- [ ] Webhook activo en Make.com con el escenario "plan-repaso →
      Iterator → Aggregator → Gmail Sender". URL en `MAKE_WEBHOOK_URL`.
- [ ] Cuenta DigitalOcean con créditos activos.
- [ ] Cuenta Vercel conectada al repositorio GitHub.
- [ ] Node 20+ y Python 3.11+ instalados localmente.

Si falta cualquiera, el agente detiene la implementación y pide al
estudiante que lo resuelva.

---

## Fase 1 — Backend: scaffolding e infraestructura

**Objetivo:** dejar el backend corriendo en local con `/health`
respondiendo OK, aunque no haga nada útil aún.

1. Crear estructura de carpetas según `spec-backend.md` sección 2.
2. Configurar `pyproject.toml` con `uv` o `poetry` y las dependencias
   de la sección 3 de la spec.
3. Crear `.env.example` con todas las variables documentadas.
4. Crear `.gitignore` que excluya `.env`, `credentials/`, `data/`,
   `__pycache__`, `.venv`, `.pytest_cache`.
5. Crear `src/settings.py` con `pydantic-settings`.
6. Crear `src/logger.py` con `loguru` configurado.
7. Crear `src/app.py` mínimo con:
   - Inicialización FastAPI.
   - Middleware CORS.
   - Middleware de `request_id`.
   - Endpoint `GET /health` que responde `{ "status": "ok", "version": "0.1.0", "qdrant_ok": false, "gemini_ok": false }`
     (sin verificar todavía).
8. Crear `Dockerfile` y `docker-compose.yml`.
9. Verificar localmente: `docker compose up` y `curl localhost:8000/health` devuelve 200.

**Criterio de aceptación de Fase 1:** `/health` responde 200 en local
con Docker. El agente NO continúa hasta confirmarlo con el estudiante.

---

## Fase 2 — Backend: servicios externos

**Objetivo:** crear los 4 wrappers de servicios externos y verificar
que las claves funcionan.

1. Crear `src/services/qdrant_client.py` con:
   - Conexión al cluster.
   - Método `ensure_collection()` que crea
     `mentor_ia_aprendizaje` (768 dim, COSINE) si no existe.
   - Método `ping()` que devuelve True/False.
2. Crear `src/services/gemini.py` con:
   - Método `embed_query(text)` → list[float] de 768 dim.
   - Método `embed_texts(texts)` → list[list[float]] por batch.
   - Método `generate(prompt, system=None)` → str.
3. Crear `src/services/vision.py` con:
   - Método `ocr(bytes, mime)` que llama a Vision REST API y devuelve
     `fullTextAnnotation.text`.
4. Crear `src/services/make_webhook.py` con:
   - Método `enviar_plan(payload)` que hace POST al webhook con
     timeout de 10s.
5. Actualizar `GET /health` para que ahora SÍ verifique Qdrant y Gemini
   (con timeout 2s cada uno) y refleje el estado real.

**Criterio de aceptación de Fase 2:** `/health` devuelve
`qdrant_ok: true` y `gemini_ok: true`. El agente NO continúa hasta
confirmarlo.

---

## Fase 3 — Backend: utilidades comunes

**Objetivo:** construir las funciones puras que los agentes usarán.

1. `src/utils/chunking.py`: función `chunkear(texto, max_chars=900, overlap=150, max_chunks=100)` que devuelve `list[str]`.
2. `src/utils/pdf_reader.py`: función `extraer_texto_pdf(path)` usando `pypdf`.
3. `src/utils/safe_filename.py`: función `safe_filename(nombre_original)` que retira path traversal y caracteres peligrosos.

Cada utilidad debe tener un test manual rápido (script independiente)
que el estudiante pueda correr y verificar el comportamiento.

---

## Fase 4 — Backend: AgenteExtraccion

**Objetivo:** poder subir un documento y verlo en Qdrant.

1. Crear `src/agentes/agente_extraccion.py` según spec sección 6.1.
2. Crear `src/models.py` con los Pydantic schemas de upload y documentos.
3. Implementar `POST /upload-document` y `GET /documentos-indexados`.
4. Probar manualmente:
   - Subir `data/ejemplos/test.pdf` (cualquier PDF de prueba).
   - Verificar en Qdrant Cloud Dashboard que aparecen chunks.
   - `GET /documentos-indexados` lista el archivo con el `total_chunks` correcto.
   - Re-subir el mismo PDF NO duplica chunks (idempotencia UUIDv5).

**Criterio de aceptación de Fase 4:** las 3 verificaciones manuales
pasan. Si falla la idempotencia, NO seguir.

---

## Fase 5 — Backend: AgenteRespuesta

**Objetivo:** consultar un PDF indexado y recibir respuesta con fuentes.

1. Crear `src/agentes/agente_respuesta.py` según spec sección 6.2.
2. Implementar `POST /query` con `QueryRequest` / `QueryResponse`.
3. Probar manualmente con el PDF ya indexado:
   - Pregunta relacionada al contenido → `origen: "rag"`, fuentes no
     vacías, respuesta cita el material.
   - Pregunta no relacionada → `origen: "modelo"`, fuentes vacías.

**Criterio de aceptación de Fase 5:** ambos casos pasan.

---

## Fase 6 — Backend: AgentePlanRepaso

**Objetivo:** generar un plan de 4 sesiones y enviarlo por correo.

1. Crear `src/agentes/agente_plan_repaso.py` según spec sección 6.3.
2. Implementar `POST /plan-repaso` aceptando ambos modos (JSON con tema, multipart con archivo).
3. Probar manualmente:
   - Modo Tema sin email: devuelve 4 sesiones.
   - Modo Tema con email: devuelve 4 sesiones + correo recibido.
   - Modo Archivo: indexa el archivo subido y genera plan basado en él.

**Criterio de aceptación de Fase 6:** los 3 casos pasan. Si el correo
no llega, debug con Make.com antes de seguir.

---

## Fase 7 — Backend: OCR

**Objetivo:** extraer texto de una imagen.

1. Implementar `POST /ocr-imagen` con `OcrResponse`.
2. Probar manualmente con una imagen (apunte escaneado, captura de
   pizarra).

**Criterio de aceptación de Fase 7:** el texto extraído coincide
razonablemente con el contenido de la imagen.

---

## Fase 8 — Frontend: scaffolding

**Objetivo:** Next.js corriendo con shell mínimo apuntando al backend.

1. Crear proyecto con `npx create-next-app@latest frontend --typescript --tailwind --app --src-dir=false --import-alias='@/*'`.
2. Confirmar versiones: Next 16.2.x, React 19, TS 5.
3. Instalar shadcn/ui: `npx shadcn@latest init` y luego añadir
   componentes uno por uno: `alert`, `badge`, `button`, `card`, `input`,
   `label`, `radio-group`, `scroll-area`, `separator`, `skeleton`,
   `tabs`, `textarea`.
4. Instalar `lucide-react`.
5. Crear `lib/types.ts` y `lib/api.ts` según spec sección 4 y 5.
6. Crear `.env.local.example`.
7. Crear `app/layout.tsx` con Inter, lang="es", metadata.
8. Crear `app/page.tsx` con los dos tabs principales vacíos.

**Criterio de aceptación de Fase 8:** `npm run dev` levanta y se ve
el header con tabs (sin contenido todavía).

---

## Fase 9 — Frontend: StudyAssistant

1. Crear `components/study-assistant.tsx` con layout dos columnas.
2. Crear sub-tabs Contexto / Documentos / OCR.
3. Crear `components/chat-message.tsx`, `components/chat-composer.tsx`.
4. Implementar el flujo: pregunta → backend → respuesta en burbuja.
5. Implementar subida de documentos en Contexto.
6. Implementar lista en Documentos.
7. Implementar OCR en su sub-tab.

**Criterio de aceptación de Fase 9:** flujo completo funciona en
local: subir → consultar → ver respuesta con fuentes.

---

## Fase 10 — Frontend: ReviewPlan

1. Crear `components/review-plan.tsx` con RadioGroup modo Tema/Archivo.
2. Crear `components/plan-timeline.tsx` con 4 tarjetas.
3. Implementar el flujo completo.

**Criterio de aceptación de Fase 10:** generar plan con email envía
el correo (verificar en bandeja de entrada).

---

## Fase 11 — Frontend: StatusIndicator

1. Crear `components/status-indicator.tsx` con healthcheck real.
2. Conectar al `GET /health` con polling cada 30s.
3. Mostrar 3 estados: Online verde / Parcial amarillo / Offline rojo.

---

## Fase 12 — Despliegue backend en DigitalOcean

1. Crear Droplet (Ubuntu 24.04, Basic Plan $6/mes con créditos Student
   Pack, datacenter NYC o SFO).
2. Configurar dominio o subdominio (opcional) o usar la IP del droplet.
3. SSH al droplet:
   - Instalar Docker y Docker Compose.
   - Crear usuario no-root.
   - Configurar firewall: solo SSH (22), HTTP (80), HTTPS (443).
4. Clonar el repo y crear `.env` con las claves reales.
5. Subir las credenciales JSON de Vision a `credentials/`.
6. `docker compose up -d`.
7. Configurar Nginx como reverse proxy con Let's Encrypt para HTTPS.
8. Verificar `https://<dominio o IP>/health` responde 200 desde
   internet.
9. Actualizar `CORS_ORIGINS` para incluir el dominio frontend.

**Criterio de aceptación de Fase 12:** la URL pública del backend
responde en `/health` con `qdrant_ok: true, gemini_ok: true`.

---

## Fase 13 — Despliegue frontend en Vercel

1. Push del repo a GitHub.
2. Importar repo en Vercel apuntando al subdirectorio `frontend/`.
3. Configurar variable `NEXT_PUBLIC_BACKEND_URL` con la URL del
   droplet DO.
4. Deploy automático.
5. Verificar que la UI carga y consume al backend real.
6. (Opcional) Configurar dominio personalizado.

**Criterio de aceptación de Fase 13:** flujo extremo a extremo
funciona en producción: abrir Vercel URL → subir documento →
consultar → recibir respuesta.

---

## Fase 14 — Smoke tests finales pre-sustentación

Una sesión completa antes del 20 de mayo:

- [ ] Indexar 3-5 documentos reales del estudiante.
- [ ] Hacer 5-10 consultas variadas, verificar que el RAG cita fuentes.
- [ ] Generar al menos 2 planes con email y verificar bandeja de
      entrada.
- [ ] Hacer al menos 3 OCR con imágenes diferentes.
- [ ] Verificar el badge "Online" en producción.
- [ ] Tomar screenshots de cada flujo para incluir en el documento
      académico.

**Criterio de aceptación final:** todos los flujos pasan y los
screenshots están listos para el documento.

---

## Lo que NO está en este plan

- Tests unitarios formales (fuera del alcance académico).
- CI/CD (deploy manual es suficiente).
- Observabilidad avanzada (Sentry, Datadog) (overkill).
- Autenticación de usuarios (explícitamente fuera de alcance).
- Internacionalización (proyecto solo español).

---

_Última actualización: 2026-05-11._
