import type {
  DocumentosResponse,
  HealthResponse,
  OcrResponse,
  PlanRepasoResponse,
  QueryResponse,
  UploadResponse,
} from "@/lib/types";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.detail ?? body?.message ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export function askQuery(pregunta: string): Promise<QueryResponse> {
  return request<QueryResponse>("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pregunta }),
  });
}

export function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/upload-document", {
    method: "POST",
    headers: { "X-Filename": file.name },
    body: form,
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
  });
}

export function ocrImage(file: File): Promise<OcrResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<OcrResponse>("/ocr-imagen", {
    method: "POST",
    body: form,
  });
}

export function getIndexedDocuments(): Promise<DocumentosResponse> {
  return request<DocumentosResponse>("/documentos-indexados");
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

