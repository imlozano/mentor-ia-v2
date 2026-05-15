"use client";

import { useMemo, useState } from "react";
import { Upload } from "lucide-react";

import { askQuery, getIndexedDocuments, uploadDocument } from "@/lib/api";
import type { DocumentoIndexado, Fuente, Origen } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ChatComposer } from "@/components/chat-composer";
import { ChatMessageItem } from "@/components/chat-message";
import { DocumentsList } from "@/components/documents-list";
import { OcrUploader } from "@/components/ocr-uploader";
import { EmptyState } from "@/components/empty-state";

type ChatMsg =
  | { role: "user"; content: string }
  | { role: "agent"; content: string; sources: Fuente[]; origen: Origen };

const EXAMPLE_QUERIES = [
  "¿Cuál es la historia de C y C++?",
  "Técnicas de prompt engineering",
  "Atajos básicos de terminal Linux",
];

export function StudyAssistant() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [docs, setDocs] = useState<DocumentoIndexado[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [leftTab, setLeftTab] = useState<"contexto" | "documentos" | "ocr">("contexto");

  async function sendQuestion(text: string) {
    setError(null);
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    try {
      const res = await askQuery(text);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: res.respuesta, sources: res.fuentes, origen: res.origen },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible consultar al backend.");
    } finally {
      setLoading(false);
    }
  }

  async function onFileUpload(file: File) {
    setError(null);
    setLoading(true);
    try {
      await uploadDocument(file);
      await refreshDocs();
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: `Documento ${file.name} indexado correctamente.`, sources: [], origen: "modelo" },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible subir el documento.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshDocs() {
    const res = await getIndexedDocuments();
    setDocs(res.documentos);
  }

  const messageView = useMemo(
    () =>
      messages.length ? (
        messages.map((msg, idx) => <ChatMessageItem key={idx} message={msg} />)
      ) : (
        <EmptyState title="Empieza una conversación" subtitle="Haz una pregunta sobre tus documentos indexados." />
      ),
    [messages],
  );

  return (
    <div className="grid gap-4 md:grid-cols-[320px_1fr]">
      <div className="space-y-3 rounded-lg border p-3">
        <Tabs value={leftTab} onValueChange={(v) => setLeftTab(v as "contexto" | "documentos" | "ocr")}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="contexto">Contexto</TabsTrigger>
            <TabsTrigger value="documentos">Documentos</TabsTrigger>
            <TabsTrigger value="ocr">OCR</TabsTrigger>
          </TabsList>

          <TabsContent value="contexto" className="space-y-3">
            <label className="block">
              <input
                type="file"
                accept=".pdf,.txt,.md,.png,.jpg,.jpeg"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void onFileUpload(file);
                }}
              />
              <Button className="w-full" type="button">
                <Upload className="mr-1 size-4" />
                + Subir documento
              </Button>
            </label>
            <div className="space-y-1 text-sm">
              {EXAMPLE_QUERIES.map((q) => (
                <Button key={q} variant="ghost" className="h-auto w-full justify-start px-2 py-1" onClick={() => void sendQuestion(q)}>
                  {q}
                </Button>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="documentos" className="space-y-3">
            <Button variant="outline" onClick={() => void refreshDocs()}>
              Refrescar lista
            </Button>
            <DocumentsList docs={docs} />
          </TabsContent>

          <TabsContent value="ocr">
            <OcrUploader />
          </TabsContent>
        </Tabs>
      </div>

      <div className="space-y-3 rounded-lg border p-3">
        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <div className="max-h-[520px] space-y-3 overflow-y-auto pr-1">{messageView}</div>

        {loading ? <p className="text-sm text-muted-foreground">Pensando...</p> : null}

        <ChatComposer onSend={sendQuestion} disabled={loading} />
      </div>
    </div>
  );
}

