import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DocumentoIndexado } from "@/lib/types";

const colorByType: Record<string, string> = {
  pdf: "bg-red-500/10 text-red-700",
  txt: "bg-blue-500/10 text-blue-700",
  md: "bg-green-500/10 text-green-700",
  image: "bg-purple-500/10 text-purple-700",
};

export function DocumentsList({ docs }: { docs: DocumentoIndexado[] }) {
  if (docs.length === 0) return <p className="text-sm text-muted-foreground">Sin documentos indexados.</p>;

  const total = docs.reduce((sum, d) => sum + d.total_chunks, 0);
  return (
    <div className="space-y-3">
      <div className="text-sm text-muted-foreground">
        Total documentos: {docs.length} · Total chunks: {total}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {docs.map((doc) => (
          <Card key={doc.source_path}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{doc.nombre_archivo}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs">
              <Badge className={colorByType[doc.tipo_fuente] || ""}>{doc.tipo_fuente.toUpperCase()}</Badge>
              <p>Chunks: {doc.total_chunks}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

