import { FileText, Image as ImageIcon } from "lucide-react";

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

export function DocumentsList({ docs }: { docs: DocumentoIndexado[] }) {
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
      <div className="space-y-1 rounded-xl bg-muted/30 p-3 text-[11px] text-muted-foreground">
        <p>
          Documentos:{" "}
          <span className="font-medium text-foreground">{docs.length}</span>
        </p>
        <p>
          Chunks: <span className="font-medium text-foreground">{total}</span>
        </p>
      </div>

      <div className="space-y-2">
        {docs.map((doc) => (
          <div
            key={doc.nombre_archivo}
            className="flex items-center justify-between gap-2 rounded-xl bg-muted/30 p-3 transition-colors hover:bg-muted/50"
          >
            <div className="flex min-w-0 flex-1 items-center gap-2.5">
              {iconFor(doc.tipo_fuente)}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium [overflow-wrap:anywhere]">
                  {doc.nombre_archivo}
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {doc.total_chunks} chunks
                </p>
              </div>
            </div>
            <Badge
              variant="outline"
              className={`shrink-0 rounded-md font-mono text-[10px] ${colorByType[doc.tipo_fuente] ?? ""}`}
            >
              {doc.tipo_fuente.toUpperCase()}
            </Badge>
          </div>
        ))}
      </div>
    </div>
  );
}
