import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearAllDocuments, deleteDocument } from "@/lib/api";

vi.mock("@/lib/session", () => ({
  getSessionId: () => "00000000-0000-4000-8000-000000000001",
}));

describe("delete API", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("deleteDocument llama DELETE al documento correcto", async () => {
    const docId = "00000000-0000-4000-8000-0000000000ab";
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "ok",
          document_id: docId,
          nombre_archivo: "a.pdf",
          chunks_eliminados: 2,
          archivo_local_eliminado: true,
        }),
        { status: 200 },
      ),
    );

    await deleteDocument(docId);

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/documentos/${encodeURIComponent(docId)}`),
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("clearAllDocuments llama DELETE /documentos", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "ok",
          documentos_eliminados: 1,
          chunks_eliminados: 2,
          archivos_locales_eliminados: 1,
        }),
        { status: 200 },
      ),
    );

    await clearAllDocuments();

    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/documentos$/),
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
