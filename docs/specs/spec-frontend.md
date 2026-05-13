# Spec — Frontend Next.js (`frontend/`)

> Especificación técnica para construir el frontend del sistema **Mentor
> IA**. Este documento lo lee el agente (Claude Code o Cursor) y produce
> el código en `frontend/`.
>
> Cualquier ambigüedad se resuelve consultando antes
> [`../academic/wireframes-frontend.md`](../academic/wireframes-frontend.md)
> y [`../academic/Flujo_Interaccion_Usuario_Sistema.md`](../academic/Flujo_Interaccion_Usuario_Sistema.md).

---

## 1. Resumen

Aplicación Next.js 16 con App Router que consume la API del backend.
Una sola pantalla con dos tabs principales (`Asistente de Estudio` /
`Plan de Repaso`) y, dentro del primero, tres sub-tabs (`Contexto`,
`Documentos`, `OCR`).

Despliegue en Vercel. La URL del backend se configura con
`NEXT_PUBLIC_BACKEND_URL`.

## 2. Stack obligatorio

- Next.js 16.2.x con App Router.
- React 19.
- TypeScript 5 con `strict: true`.
- Tailwind CSS 4 (`@tailwindcss/postcss`).
- shadcn/ui sobre Radix Primitives.
- lucide-react para iconografía.
- Sin librerías de estado globales (Zustand, Redux). React state es
  suficiente para el alcance.

## 3. Estructura de archivos

```
frontend/
├── package.json
├── tsconfig.json
├── next.config.ts
├── tailwind.config.ts             (si Tailwind 4 lo requiere)
├── postcss.config.mjs
├── .env.local.example
├── .gitignore
├── app/
│   ├── layout.tsx                 Root layout (Inter, lang="es")
│   ├── globals.css                Variables Tailwind 4 + tokens
│   └── page.tsx                   Página única con los 2 tabs
├── components/
│   ├── study-assistant.tsx        Tab Asistente de Estudio
│   ├── review-plan.tsx            Tab Plan de Repaso
│   ├── chat-message.tsx           Burbuja de chat (usuario / agente)
│   ├── chat-composer.tsx          Input + botón enviar
│   ├── documents-list.tsx         Lista de documentos indexados
│   ├── ocr-uploader.tsx           Dropzone OCR + textarea resultado
│   ├── plan-timeline.tsx          4 tarjetas D+1/D+7/D+14/D+30
│   ├── status-indicator.tsx       Badge "Online" con healthcheck real
│   ├── empty-state.tsx            Componente reutilizable de estado vacío
│   └── ui/                        Componentes shadcn (alert, badge, button, card, input, label, radio-group, scroll-area, separator, skeleton, tabs, textarea)
├── lib/
│   ├── api.ts                     Cliente HTTP del backend
│   ├── types.ts                   Tipos TS compartidos
│   └── utils.ts                   `cn()` helper de shadcn
└── public/
    └── icons/                     (favicons, etc.)
```

## 4. Tipos compartidos (`lib/types.ts`)

Espejo de los modelos Pydantic del backend:

```typescript
export type Origen = "rag" | "modelo";

export interface Fuente {
  archivo: string;
  chunk_index: number;
  score: number;
  excerpt: string;
}

export interface QueryResponse {
  respuesta: string;
  origen: Origen;
  fuentes: Fuente[];
  detalle_origen?: string;
}

export type SesionTipo = "D+1" | "D+7" | "D+14" | "D+30";

export interface SesionPlan {
  tipo: SesionTipo;
  fecha: string;          // ISO date
  titulo: string;
  descripcion: string[];
}

export interface PlanRepasoResponse {
  tema: string;
  fecha_inicio: string;
  sesiones: SesionPlan[];
  email_enviado: boolean;
}

export type TipoFuente = "pdf" | "txt" | "md" | "image";

export interface DocumentoIndexado {
  nombre_archivo: string;
  source_path: string;
  tipo_fuente: TipoFuente;
  total_chunks: number;
}

export interface DocumentosResponse {
  documentos: DocumentoIndexado[];
  total_chunks: number;
  total_documentos: number;
}

export interface UploadResponse {
  status: "ok";
  archivo: string;
  chunks_ingresados: number;
}

export interface OcrResponse {
  texto: string;
  caracteres: number;
}

export interface HealthResponse {
  status: "ok";
  version: string;
  qdrant_ok: boolean;
  gemini_ok: boolean;
}
```

## 5. Cliente API (`lib/api.ts`)

Un archivo único con funciones tipadas. NO usar SWR, React Query u otra
librería: fetch nativo con tipos es suficiente para esta cantidad de
endpoints.

```typescript
const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL!;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.message ?? res.statusText);
  }
  return res.json();
}

export async function askQuery(pregunta: string): Promise<QueryResponse> { ... }
export async function uploadDocument(file: File): Promise<UploadResponse> { ... }
export async function createPlan(input: {
  tema: string;
  fecha_inicio: string;
  email?: string;
  archivo?: File;
}): Promise<PlanRepasoResponse> { ... }
export async function ocrImage(file: File): Promise<OcrResponse> { ... }
export async function getIndexedDocuments(): Promise<DocumentosResponse> { ... }
export async function getHealth(): Promise<HealthResponse> { ... }
```

Exportar también una clase `ApiError extends Error` con `status` para
distinguir códigos en la UI.

## 6. Pantallas y comportamiento

### 6.1 Layout raíz (`app/layout.tsx`)

- `lang="es"`.
- Cargar fuente Inter desde `next/font/google`.
- Metadata:
  - `title`: "Mentor IA — Asistente inteligente de aprendizaje"
  - `description`: "Prototipo multiagente con RAG (PDFs + OCR de
    imágenes) para apoyar tu estudio."
- Aplicar `min-h-screen bg-background text-foreground` al `<body>`.

### 6.2 Página principal (`app/page.tsx`)

Layout vertical:

1. Header global (logo + título + subtítulo + `StatusIndicator`).
2. Tabs principales centradas: `Asistente de Estudio` | `Plan de Repaso`.
3. Contenido del tab activo, ocupando el viewport.

Estado del tab activo: `useState<"asistente" | "plan">("asistente")`.

### 6.3 `StudyAssistant` (Tab "Asistente de Estudio")

Layout de dos columnas en desktop (`md+`), apilado en mobile:

- **Columna izquierda (sub-navegación):** sub-tabs verticales
  `Contexto`, `Documentos`, `OCR`. En cada sub-tab el contenido lateral
  cambia:
  - `Contexto`: botón `+ Subir documento` + texto soportes + lista de
    sugerencias (3 hardcoded).
  - `Documentos`: lista de `DocumentoIndexado`.
  - `OCR`: dropzone + botones de carga.

- **Columna derecha (chat):** mismo chat con scroll, composer, aviso
  legal, siempre visible independiente del sub-tab activo a la
  izquierda.

Sugerencias hardcoded a usar:

```typescript
const EXAMPLE_QUERIES = [
  "¿Cuál es la historia de C y C++?",
  "Técnicas de prompt engineering",
  "Atajos básicos de terminal Linux",
];
```

### 6.4 Chat (`chat-message.tsx` + `chat-composer.tsx`)

Burbuja por mensaje:

```typescript
type ChatMessage =
  | { role: "user"; content: string }
  | { role: "agent"; content: string; sources: Fuente[]; origen: Origen };
```

- Mensajes de usuario: alineados derecha, fondo `bg-primary`.
- Mensajes de agente: alineados izquierda, fondo `bg-muted`.
- Si `origen === "rag"`: header con badge "RAG · N fuentes" + lista de
  fuentes plegable.
- Si `origen === "modelo"`: badge "Conocimiento general" sin fuentes.
- Estado de carga: tres puntos animados mientras se espera respuesta.

### 6.5 `DocumentsList`

Cada tarjeta:

- Badge de tipo con color (`PDF` rojo, `TXT` azul, `MD` verde,
  `image` morado).
- Nombre del archivo.
- `total_chunks` y tipo.
- Si tienes una fecha real, mostrarla relativa
  ("hace 2 días"); si no, omitir el campo.

Header: total documentos · total chunks como badge.

Footer: `Total: N chunks` · `Formatos: ...` · `Estado: Indexados ✓`.

### 6.6 `OcrUploader`

Layout split horizontal en desktop (`md+`), apilado en mobile:

- **Izquierda:** dropzone (`border-dashed`), botón "Seleccionar archivo",
  badges informativos "Máx. 10 MB" y "Google Vision AI".
- **Derecha:** textarea de solo lectura con `texto` del response.
  Debajo, dos botones: `Copiar texto` (al portapapeles) y
  `Indexar documento` (genera un `.txt` con el contenido y llama a
  `uploadDocument`).

**Nota crítica:** en el frontend desplegado actual, este tab muestra
el chat en lugar del textarea de OCR. Para esta versión nueva
**el textarea SÍ debe estar en la columna derecha cuando se está en el
tab OCR**, no el chat. Esto alinea la UI real con los wireframes.

### 6.7 `ReviewPlan` (Tab "Plan de Repaso")

Vista de una sola columna:

- RadioGroup: modo `Tema` | modo `Archivo`.
- Si modo `Tema`: input `tema` (requerido).
- Si modo `Archivo`: input file (PDF/TXT/MD) + input `tema`
  (extraído o editable).
- Input `fecha_inicio` con datepicker nativo HTML5.
- Input `email` (opcional, type email).
- Botón "Generar plan de repaso".

Resultado: timeline con 4 tarjetas (D+1/D+7/D+14/D+30). Cada tarjeta:

- Badge con tipo de sesión.
- Fecha localizada (DD/MM/YYYY).
- Título.
- Descripción como lista.

Si `email_enviado === true`: banner verde "Plan enviado a tu correo".

### 6.8 `StatusIndicator`

Badge "Online" verde / "Offline" rojo / "Verificando…" gris.

Lógica:

- Al montar, llamar a `getHealth()`.
- Cada 30 segundos repetir.
- Si `qdrant_ok && gemini_ok`: verde "Online".
- Si responde pero alguno está `false`: amarillo "Parcial".
- Si no responde: rojo "Offline".

Esto reemplaza el badge decorativo actual.

## 7. Estados estandarizados

Patrón obligatorio: cada vista con datos del backend debe manejar 4
estados explícitos.

```typescript
type DataState<T> =
  | { status: "loading" }
  | { status: "empty" }
  | { status: "error"; message: string }
  | { status: "success"; data: T };
```

- **Loading:** `Skeleton` de shadcn del tamaño de los elementos reales.
- **Empty:** componente `EmptyState` con icono + título + subtítulo +
  CTA opcional.
- **Error:** `Alert variant="destructive"` con `AlertCircle` + mensaje.
- **Success:** datos renderizados.

## 8. Responsive

Breakpoints Tailwind 4 por defecto:

| Breakpoint | Ancho   | Reglas                                             |
| ---------- | ------- | -------------------------------------------------- |
| Base       | <640px  | Todo apilado. Sub-tabs como tabs horizontales.     |
| `sm`       | ≥640px  | Tarjetas Documentos en 2 columnas.                 |
| `md`       | ≥768px  | Asistente en 2 columnas (sidebar + chat).          |
| `lg`       | ≥1024px | Sidebar más amplia, padding aumentado.             |

Composer del chat: `pb-[env(safe-area-inset-bottom)]` para iOS.

## 9. Variables de entorno

`.env.local.example`:

```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

En producción (Vercel): `NEXT_PUBLIC_BACKEND_URL=https://api.mentor-ia.tu-dominio.com`.

## 10. Tokens de diseño

En `globals.css`, definir tokens Tailwind 4:

```css
@theme {
  --color-background: oklch(98% 0 0);
  --color-foreground: oklch(15% 0 0);
  --color-primary: oklch(50% 0.18 250);
  --color-primary-foreground: oklch(98% 0 0);
  --color-muted: oklch(95% 0 0);
  --color-muted-foreground: oklch(40% 0 0);
  --color-border: oklch(90% 0 0);
  --color-destructive: oklch(55% 0.20 25);
  --color-success: oklch(55% 0.15 145);
  --radius: 0.625rem;
}
```

Modo oscuro: agregar bloque `@media (prefers-color-scheme: dark)` con
tokens equivalentes invertidos. No incluir toggle manual en esta
versión (queda para mejora futura).

## 11. Accesibilidad

- Cada botón con `aria-label` cuando solo tiene icono.
- Inputs siempre asociados a un `<Label htmlFor>`.
- Focus visible: que Tailwind no elimine los outlines.
- Contraste mínimo AA (4.5:1) para todo texto.

## 12. Lo que NO debe hacer el agente

- No usar SWR, React Query, ni cualquier librería de fetching.
- No usar Zustand, Redux, ni otro estado global.
- No usar tRPC.
- No agregar Storybook (overkill para este alcance).
- No usar `useEffect` para fetch inicial; preferir Server Components
  cuando aplique (aunque por la naturaleza interactiva del chat, gran
  parte serán Client Components con `"use client"`).
- No agregar i18n; el proyecto es solo español.

## 13. Criterios de aceptación

El frontend está terminado cuando:

- [ ] `npm run dev` arranca sin errores ni warnings de TypeScript.
- [ ] `npm run build` produce un build sin errores.
- [ ] `npm run lint` pasa limpio.
- [ ] Subir un PDF desde la UI muestra mensaje de éxito en el chat.
- [ ] Hacer una consulta muestra burbuja con respuesta y fuentes (si
      hay match RAG).
- [ ] Generar un plan muestra los 4 tarjetones D+1/D+7/D+14/D+30.
- [ ] OCR muestra el texto extraído en el textarea y permite
      copiar/indexar.
- [ ] El badge "Online" refleja el estado real del backend.
- [ ] El layout funciona en móvil (375px) y desktop (1280px+).
- [ ] No hay `console.log` ni `console.error` en código de producción.

---

_Última actualización: 2026-05-11._
