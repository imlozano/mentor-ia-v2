"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, FileText, Sparkles, Trash2, Upload, X } from "lucide-react";

import { askQuery, getIndexedDocuments, uploadDocument } from "@/lib/api";
import type { DocumentoIndexado, Fuente, MensajeHistorial, Origen } from "@/lib/types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  "Técnicas principales de prompt engineering",
  "Atajos básicos de la terminal Linux",
];

export function StudyAssistant() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [docs, setDocs] = useState<DocumentoIndexado[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [leftTab, setLeftTab] = useState<"contexto" | "documentos" | "ocr">(
    "contexto",
  );
  const [selectedDocument, setSelectedDocument] = useState<DocumentoIndexado | null>(
    null,
  );

  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void refreshDocs();
  }, []);

  useEffect(() => {
    if (!scrollRef.current) return;
    const viewport = scrollRef.current.querySelector(
      "[data-radix-scroll-area-viewport]",
    );
    if (viewport) viewport.scrollTop = viewport.scrollHeight;
  }, [messages, loading]);

  async function refreshDocs() {
    try {
      const res = await getIndexedDocuments();
      setDocs(res.documentos);
    } catch {
      // silencioso: el StatusIndicator ya muestra estado del backend
    }
  }

  async function sendQuestion(text: string) {
    setError(null);
    setLoading(true);
    // Capturar historial ANTES de añadir el mensaje actual (máximo 6 mensajes)
    const historial: MensajeHistorial[] = messages.slice(-6).map((m) => ({
      role: m.role as "user" | "agent",
      content: m.role === "agent" ? m.content.slice(0, 1000) : m.content,
    }));
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    try {
      const res = await askQuery(text, historial, selectedDocument?.document_id ?? null);
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: res.respuesta,
          sources: res.fuentes,
          origen: res.origen,
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible consultar al backend.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function onFileUpload(file: File) {
    setError(null);
    setUploading(true);
    try {
      const res = await uploadDocument(file);
      await refreshDocs();
      if (res.document_id) {
        setSelectedDocument({
          document_id: res.document_id,
          nombre_archivo: res.archivo,
          tipo_fuente: file.name.endsWith(".pdf")
            ? "pdf"
            : file.name.endsWith(".md")
              ? "md"
              : file.name.match(/\.(png|jpg|jpeg)$/i)
                ? "image"
                : "txt",
          total_chunks: res.chunks_ingresados,
        });
      }
      const aviso = res.aviso ? ` ${res.aviso}` : "";
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: `Documento ${file.name} indexado correctamente.${aviso}`,
          sources: [],
          origen: "modelo",
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible subir el documento.",
      );
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const messageView = useMemo(() => {
    if (messages.length === 0) {
      return (
        <EmptyState
          title="¿En qué puedo ayudarte hoy?"
          subtitle="Sube un documento o haz una pregunta para comenzar."
        />
      );
    }
    return (
      <div className="space-y-5">
        {messages.map((msg, idx) => (
          <ChatMessageItem key={idx} message={msg} />
        ))}
        {loading ? (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-muted/60 px-4 py-3">
              <div className="flex gap-1.5">
                <span className="h-2 w-2 animate-bounce rounded-full bg-primary/40 [animation-delay:-0.3s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-primary/40 [animation-delay:-0.15s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-primary/40" />
              </div>
            </div>
          </div>
        ) : null}
      </div>
    );
  }, [messages, loading]);

  return (
    <div className="grid min-h-[calc(100vh-10rem)] grid-cols-1 gap-6 lg:grid-cols-12">
      <aside className="flex flex-col gap-4 lg:col-span-3">
        <div className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm">
          <Tabs
            value={leftTab}
            onValueChange={(v) => setLeftTab(v as typeof leftTab)}
            className="flex h-full flex-col"
          >
            <div className="px-3 pb-2 pt-3">
              <TabsList className="grid h-9 w-full grid-cols-3 rounded-xl bg-muted/50 p-0.5">
                <TabsTrigger
                  value="contexto"
                  className="rounded-lg text-xs data-[state=active]:bg-background data-[state=active]:shadow-sm"
                >
                  Contexto
                </TabsTrigger>
                <TabsTrigger
                  value="documentos"
                  className="rounded-lg text-xs data-[state=active]:bg-background data-[state=active]:shadow-sm"
                >
                  Documentos
                </TabsTrigger>
                <TabsTrigger
                  value="ocr"
                  className="rounded-lg text-xs data-[state=active]:bg-background data-[state=active]:shadow-sm"
                >
                  OCR
                </TabsTrigger>
              </TabsList>
            </div>

            <div className="flex-1 overflow-hidden">
              <TabsContent value="contexto" className="m-0 h-full">
                <ScrollArea className="h-full">
                  <div className="space-y-5 p-4">
                    <div className="space-y-2.5">
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.txt,.md,.png,.jpg,.jpeg"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) void onFileUpload(file);
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border px-4 py-3 text-sm text-muted-foreground transition-all hover:border-primary/50 hover:bg-primary/5 hover:text-foreground disabled:opacity-60"
                      >
                        {uploading ? (
                          <span className="animate-pulse">Subiendo...</span>
                        ) : (
                          <>
                            <Upload className="h-4 w-4" />
                            Subir documento
                          </>
                        )}
                      </button>
                      <p className="text-center text-[11px] text-muted-foreground">
                        Soporta PDF, TXT, MD e imágenes.
                      </p>
                    </div>

                    <div className="h-px bg-border/60" />

                    <div className="space-y-2">
                      <h4 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                        Sugerencias
                      </h4>
                      <div className="flex flex-col gap-1">
                        {EXAMPLE_QUERIES.map((q) => (
                          <button
                            key={q}
                            type="button"
                            onClick={() => void sendQuestion(q)}
                            disabled={loading}
                            className="rounded-lg px-3 py-2.5 text-left text-xs leading-relaxed text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground disabled:opacity-50"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="documentos" className="m-0 h-full">
                <ScrollArea className="h-full">
                  <div className="space-y-4 p-4">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-primary/70" />
                      <h3 className="text-sm font-medium">
                        Documentos indexados
                      </h3>
                    </div>
                    <DocumentsList
                      docs={docs}
                      selectedDocumentId={selectedDocument?.document_id}
                      onSelect={(doc) =>
                        setSelectedDocument((prev) =>
                          prev?.document_id === doc.document_id ? null : doc,
                        )
                      }
                    />
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="ocr" className="m-0 h-full">
                <ScrollArea className="h-full">
                  <div className="p-4">
                    <OcrUploader
                      onIndexed={async (docId, archivo, chunks) => {
                        await refreshDocs();
                        setSelectedDocument({
                          document_id: docId,
                          nombre_archivo: archivo,
                          tipo_fuente: "txt",
                          total_chunks: chunks,
                        });
                      }}
                    />
                  </div>
                </ScrollArea>
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </aside>

      <section className="flex flex-col gap-4 lg:col-span-9">
        <div className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary/70" />
              <span className="text-sm font-medium">Chat con Mentor IA</span>
            </div>
            {messages.length > 0 ? (
              <button
                type="button"
                onClick={() => setMessages([])}
                className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-destructive"
                title="Borrar historial"
                aria-label="Borrar historial"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            ) : null}
          </div>

          {selectedDocument ? (
            <div className="flex items-center justify-between gap-2 border-b border-border/60 bg-primary/5 px-5 py-2 text-xs">
              <span>
                Consultando:{" "}
                <span className="font-medium">{selectedDocument.nombre_archivo}</span>
              </span>
              <button
                type="button"
                onClick={() => setSelectedDocument(null)}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                aria-label="Quitar selección de documento"
              >
                <X className="h-3.5 w-3.5" />
                Quitar
              </button>
            </div>
          ) : null}

          <ScrollArea ref={scrollRef} className="flex-1">
            <div className="min-h-[400px] p-5">{messageView}</div>
          </ScrollArea>

          {error ? (
            <div className="px-5 pb-3">
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            </div>
          ) : null}

          <div className="border-t border-border/60 bg-background/40 p-4">
            <ChatComposer onSend={sendQuestion} disabled={loading} />
          </div>
        </div>
      </section>
    </div>
  );
}
