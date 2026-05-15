"use client";

import { useState } from "react";

import { ocrImage, uploadDocument } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";

export function OcrUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function runOcr() {
    if (!file) return;
    setBusy(true);
    try {
      const res = await ocrImage(file);
      setText(res.texto);
    } finally {
      setBusy(false);
    }
  }

  async function indexText() {
    if (!text.trim()) return;
    const blob = new Blob([text], { type: "text/plain" });
    const txtFile = new File([blob], "ocr-extraido.txt", { type: "text/plain" });
    setBusy(true);
    try {
      await uploadDocument(txtFile);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="space-y-3 rounded-lg border border-dashed p-4">
        <p className="text-sm font-medium">OCR de imagen</p>
        <div className="flex gap-2">
          <Badge>Máx. 10 MB</Badge>
          <Badge variant="secondary">Gemini multimodal</Badge>
        </div>
        <input type="file" accept=".png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <Button onClick={() => void runOcr()} disabled={!file || busy}>
          Ejecutar OCR
        </Button>
      </div>

      <div className="space-y-3">
        <Textarea value={text} readOnly className="min-h-48" placeholder="Texto extraído aparecerá aquí..." />
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={() => navigator.clipboard.writeText(text)} disabled={!text}>
            Copiar texto
          </Button>
          <Button type="button" onClick={() => void indexText()} disabled={!text || busy}>
            Indexar documento
          </Button>
        </div>
      </div>
    </div>
  );
}

