import { describe, expect, it } from "vitest";

import { buildQueryBody } from "@/lib/build-query-body";

describe("buildQueryBody", () => {
  it("incluye document_id cuando hay selección", () => {
    const body = buildQueryBody("Explícame este documento", [], "doc-123");
    expect(body.document_id).toBe("doc-123");
    expect(body.pregunta).toBe("Explícame este documento");
  });

  it("omite document_id sin selección", () => {
    const body = buildQueryBody("hola", []);
    expect(body.document_id).toBeUndefined();
  });
});
