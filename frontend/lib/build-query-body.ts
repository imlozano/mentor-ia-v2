import type { MensajeHistorial, QueryModo } from "@/lib/types";

export function buildQueryBody(
  pregunta: string,
  historial: MensajeHistorial[] = [],
  documentId?: string | null,
  modo: QueryModo = "auto",
) {
  return {
    pregunta,
    historial,
    ...(documentId ? { document_id: documentId } : {}),
    modo,
  };
}
