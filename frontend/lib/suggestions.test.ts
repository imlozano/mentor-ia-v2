import { describe, expect, it } from "vitest";

import { buildSuggestions, clearSelectionIfDeleted } from "@/lib/suggestions";
import type { DocumentoIndexado } from "@/lib/types";

const doc: DocumentoIndexado = {
  document_id: "00000000-0000-4000-8000-000000000099",
  nombre_archivo: "a.pdf",
  tipo_fuente: "pdf",
  total_chunks: 3,
};

describe("buildSuggestions", () => {
  it("con documento seleccionado sugiere acciones documentales", () => {
    const items = buildSuggestions([doc], doc);
    expect(items[0]).toBe("Resume el documento seleccionado");
    expect(items).toHaveLength(4);
  });

  it("sin selección pero con docs sugiere seleccionar", () => {
    const items = buildSuggestions([doc], null);
    expect(items[0]).toContain("Selecciona");
  });

  it("sin docs sugiere subir", () => {
    const items = buildSuggestions([], null);
    expect(items[0]).toContain("Sube");
  });
});

describe("clearSelectionIfDeleted", () => {
  it("limpia cuando coincide el id borrado", () => {
    expect(clearSelectionIfDeleted(doc.document_id, doc.document_id)).toBe(true);
  });

  it("no limpia si es otro documento", () => {
    expect(clearSelectionIfDeleted(doc.document_id, "other-id")).toBe(false);
  });
});
