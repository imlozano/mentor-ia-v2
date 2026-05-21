export type Origen = "rag" | "modelo";

export interface MensajeHistorial {
  role: "user" | "agent";
  content: string;
}

export interface Fuente {
  archivo: string;
  chunk_index: number;
  score?: number | null;
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
  fecha: string;
  titulo: string;
  descripcion: string[];
}

export interface PlanRepasoResponse {
  tema: string;
  fecha_inicio: string;
  sesiones: SesionPlan[];
  email_enviado: boolean;
  chunks_ingresados?: number | null;
}

export type TipoFuente = "pdf" | "txt" | "md" | "image";

export interface DocumentoIndexado {
  document_id: string;
  nombre_archivo: string;
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
  document_id?: string | null;
  aviso?: string | null;
}

export interface OcrResponse {
  texto: string;
  caracteres: number;
}

export interface HealthResponse {
  status: "ok";
  version: string;
  qdrant_ok: boolean;
  openai_ok: boolean;
}


export interface DeleteDocumentoResponse {
  status: "ok";
  document_id: string;
  nombre_archivo: string;
  chunks_eliminados: number;
  archivo_local_eliminado: boolean;
}

export interface VaciarDocumentosResponse {
  status: "ok";
  documentos_eliminados: number;
  chunks_eliminados: number;
  archivos_locales_eliminados: number;
}

export type QueryModo = "auto" | "documento" | "general";
