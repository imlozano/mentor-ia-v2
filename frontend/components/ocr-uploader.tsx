"use client";

import { useRef, useState } from "react";
import { Copy, FileImage, ScanLine } from "lucide-react";

import { ocrImage, uploadDocument } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function OcrUploader() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function onPick(file: File) {
    setError(null);
    setBusy(true);
    setText("");
    setFileName(file.name);
    try {
      const res = await ocrImage(file);
      setText(res.texto || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al procesar la imagen.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function copyText() {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // fallback silencioso
    }
  }

  async function indexText() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const blob = new Blob([text], { type: "text/plain" });
      const txtFile = new File([blob], "ocr-extraido.txt", {
        type: "text/plain",
      });
      await uploadDocument(txtFile);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible indexar el texto.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FileImage className="h-4 w-4 text-primary/70" />
        <h3 className="text-sm font-medium">OCR de imágenes</h3>
      </div>

      <div className="space-y-2.5">
        <input
          ref={inputRef}
          type="file"
          accept=".png,.jpg,.jpeg"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void onPick(file);
          }}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border px-4 py-3 text-sm text-muted-foreground transition-all hover:border-primary/50 hover:bg-primary/5 hover:text-foreground disabled:opacity-60"
        >
          {busy ? (
            <span className="animate-pulse">Procesando...</span>
          ) : (
            <>
              <ScanLine className="h-4 w-4" />
              Subir imagen
            </>
          )}
        </button>
        <p className="text-center text-[11px] text-muted-foreground">
          Soporta PNG, JPG, JPEG.
        </p>
        {fileName ? (
          <p className="truncate rounded-md bg-muted/40 px-2 py-1 text-[11px] text-muted-foreground">
            {fileName}
          </p>
        ) : null}
      </div>

      {error ? (
        <p className="rounded-md bg-destructive/10 px-2 py-1.5 text-[11px] text-destructive">
          {error}
        </p>
      ) : null}

      {text ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Texto extraído
            </h4>
            <button
              type="button"
              onClick={() => void copyText()}
              className="flex items-center gap-1 text-[11px] font-medium text-primary transition-colors hover:text-primary/80"
            >
              <Copy className="h-3 w-3" />
              Copiar
            </button>
          </div>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="min-h-[160px] rounded-xl border-0 bg-muted/30 text-xs leading-relaxed focus-visible:ring-1 focus-visible:ring-primary/40"
          />
          <Button
            type="button"
            onClick={() => void indexText()}
            disabled={!text.trim() || busy}
            size="sm"
            className="w-full rounded-lg"
          >
            Indexar este texto
          </Button>
        </div>
      ) : null}
    </div>
  );
}
