import { CheckCircle2, FileText, Image as ImageIcon, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { DocumentoIndexado } from "@/lib/types";

const colorByType: Record<string, string> = {
  pdf: "bg-red-500/10 text-red-700 dark:text-red-300 border-transparent",
  txt: "bg-blue-500/10 text-blue-700 dark:text-blue-300 border-transparent",
  md: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-transparent",
  image:
    "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-transparent",
};

function iconFor(tipo: string) {
  if (tipo === "image") return <ImageIcon className="h-3.5 w-3.5 text-primary/70" />;
  return <FileText className="h-3.5 w-3.5 text-primary/70" />;
}

interface DocumentsListProps {
  docs: DocumentoIndexado[];
  selectedDocumentId?: string | null;
  onSelect?: (doc: DocumentoIndexado) => void;
  onDelete?: (doc: DocumentoIndexado) => void;
  onClearAll?: () => void;
  clearing?: boolean;
}

export function DocumentsList({
  docs,
  selectedDocumentId,
  onSelect,
  onDelete,
  onClearAll,
  clearing = false,
}: DocumentsListProps) {
  if (docs.length === 0) {
    return (
      <p className="px-1 text-xs text-muted-foreground">
        No hay documentos indexados todavía.
      </p>
    );
  }

  const total = docs.reduce((sum, d) => sum + d.total_chunks, 0);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="space-y-1 rounded-xl bg-muted/30 p-3 text-[11px] text-muted-foreground">
          <p>
            Documentos:{" "}
            <span className="font-medium text-foreground">{docs.length}</span>
          </p>
          <p>
            Chunks: <span className="font-medium text-foreground">{total}</span>
          </p>
        </div>
        {onClearAll ? (
          <button
            type="button"
            onClick={onClearAll}
            disabled={clearing}
            className="shrink-0 rounded-lg border border-destructive/30 px-2 py-1 text-[10px] text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"
          >
            {clearing ? "Vaciando..." : "Vaciar"}
          </button>
        ) : null}
      </div>

      <div className="space-y-2">
        {docs.map((doc) => {
          const selected = selectedDocumentId === doc.document_id;
          return (
            <div
              key={doc.document_id}
              className={`flex w-full items-center justify-between gap-2 rounded-xl p-3 transition-colors ${
                selected
                  ? "bg-primary/10 ring-1 ring-primary/40"
                  : "bg-muted/30 hover:bg-muted/50"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelect?.(doc)}
                className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
              >
                {selected ? (
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-primary" />
                ) : (
                  iconFor(doc.tipo_fuente)
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium [overflow-wrap:anywhere]">
                    {doc.nombre_archivo}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {doc.total_chunks} chunks
                  </p>
                </div>
              </button>
              <div className="flex shrink-0 items-center gap-1">
                <Badge
                  variant="outline"
                  className={`rounded-md font-mono text-[10px] ${colorByType[doc.tipo_fuente] ?? ""}`}
                >
                  {doc.tipo_fuente.toUpperCase()}
                </Badge>
                {onDelete ? (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(doc);
                    }}
                    className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                    title="Eliminar documento"
                    aria-label={`Eliminar ${doc.nombre_archivo}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
