import type { SesionPlan } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function PlanTimeline({ sessions }: { sessions: SesionPlan[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {sessions.map((s) => (
        <Card key={`${s.tipo}-${s.fecha}`}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <Badge>{s.tipo}</Badge>
              <span className="text-xs text-muted-foreground">
                {new Date(s.fecha).toLocaleDateString("es-CO")}
              </span>
            </div>
            <CardTitle className="text-sm">{s.titulo}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <ul className="list-disc space-y-1 pl-5">
              {s.descripcion.map((d, idx) => (
                <li key={idx}>{d}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

