import { buildQueryBody } from "@/lib/build-query-body";
import type {
  DocumentosResponse,
  HealthResponse,
  MensajeHistorial,
  OcrResponse,
  PlanRepasoResponse,
  QueryModo,
  QueryResponse,
  UploadResponse,
  DeleteDocumentoResponse,
  VaciarDocumentosResponse,
} from "@/lib/types";
import { getSessionId } from "@/lib/session";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// Timeouts por defecto. OCR y plan-repaso hacen varias llamadas a OpenAI,
// así que se les concede una ventana más amplia.
const DEFAULT_TIMEOUT_MS = 30_000;
const LONG_TIMEOUT_MS = 60_000;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

interface RequestOptions extends RequestInit {
  /** Timeout en ms; si se supera se aborta y se lanza un ApiError claro. */
  timeoutMs?: number;
}

async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, headers, ...rest } = init;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BACKEND}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        ...headers,
        "X-Session-ID": getSessionId(),
      },
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({} as Record<string, unknown>));
      const detail =
        typeof body?.detail === "string"
          ? body.detail
          : typeof body?.message === "string"
            ? body.message
            : res.status >= 500
              ? `Error del servidor (${res.status}). Inténtalo de nuevo.`
              : undefined;
      if (res.status === 404) {
        throw new ApiError(404, detail ?? "No encontré ese documento en esta sesión.");
      }
      if (res.status === 422) {
        throw new ApiError(422, detail ?? "El documento existe pero no tiene chunks indexados.");
      }
      if (res.status === 429) {
        throw new ApiError(
          429,
          detail ??
            "Has hecho demasiadas solicitudes seguidas. Espera un momento e inténtalo de nuevo.",
        );
      }
      throw new ApiError(res.status, detail ?? res.statusText);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(
        0,
        "La solicitud tardó demasiado y se canceló. Revisa tu conexión e inténtalo de nuevo.",
      );
    }
    throw new ApiError(
      0,
      "No fue posible contactar con el backend. Revisa tu conexión.",
    );
  } finally {
    clearTimeout(timer);
  }
}

export function askQuery(
  pregunta: string,
  historial: MensajeHistorial[] = [],
  documentId?: string | null,
  modo: QueryModo = "auto",
): Promise<QueryResponse> {
  return request<QueryResponse>("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildQueryBody(pregunta, historial, documentId, modo)),
  });
}

export function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/upload-document", {
    method: "POST",
    headers: { "X-Filename": file.name },
    body: form,
    timeoutMs: LONG_TIMEOUT_MS,
  });
}

export async function createPlan(input: {
  tema: string;
  fecha_inicio: string;
  email?: string;
  archivo?: File;
}): Promise<PlanRepasoResponse> {
  if (input.archivo) {
    const form = new FormData();
    form.append("tema", input.tema);
    form.append("fecha_inicio", input.fecha_inicio);
    if (input.email) form.append("email", input.email);
    form.append("file", input.archivo);
    return request<PlanRepasoResponse>("/plan-repaso", {
      method: "POST",
      body: form,
      timeoutMs: LONG_TIMEOUT_MS,
    });
  }

  return request<PlanRepasoResponse>("/plan-repaso", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tema: input.tema,
      fecha_inicio: input.fecha_inicio,
      email: input.email || null,
    }),
    timeoutMs: LONG_TIMEOUT_MS,
  });
}

export function ocrImage(file: File): Promise<OcrResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<OcrResponse>("/ocr-imagen", {
    method: "POST",
    body: form,
    timeoutMs: LONG_TIMEOUT_MS,
  });
}

export function getIndexedDocuments(): Promise<DocumentosResponse> {
  return request<DocumentosResponse>("/documentos-indexados");
}

export function deleteDocument(documentId: string): Promise<DeleteDocumentoResponse> {
  return request<DeleteDocumentoResponse>(`/documentos/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
}

export function clearAllDocuments(): Promise<VaciarDocumentosResponse> {
  return request<VaciarDocumentosResponse>("/documentos", {
    method: "DELETE",
  });
}


export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}
