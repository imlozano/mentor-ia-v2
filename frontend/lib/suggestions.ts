import type { DocumentoIndexado } from "@/lib/types";

const WITH_SELECTION = [
  "Resume el documento seleccionado",
  "Explícame los conceptos clave",
  "Hazme preguntas tipo examen",
  "¿Qué partes debería repasar?",
];

const WITHOUT_SELECTION_HAS_DOCS = [
  "Selecciona un documento en la pestaña Documentos",
  "Sube un PDF o TXT para consultar con RAG",
];

const WITHOUT_DOCS = [
  "Sube un documento para empezar",
  "Selecciona un documento después de indexarlo",
];

export function buildSuggestions(
  docs: DocumentoIndexado[],
  selectedDocument: DocumentoIndexado | null,
): string[] {
  if (selectedDocument) {
    return WITH_SELECTION;
  }
  if (docs.length > 0) {
    return WITHOUT_SELECTION_HAS_DOCS;
  }
  return WITHOUT_DOCS;
}

export function clearSelectionIfDeleted(
  selectedDocumentId: string | null | undefined,
  deletedDocumentId: string,
): boolean {
  return selectedDocumentId === deletedDocumentId;
}
