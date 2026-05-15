import { CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { SesionPlan } from "@/lib/types";

export function PlanTimeline({ sessions }: { sessions: SesionPlan[] }) {
  return (
    <div className="relative">
      <div className="absolute bottom-6 left-3 top-6 hidden w-px bg-border/60 md:block" />

      <div className="space-y-4">
        {sessions.map((session, idx) => (
          <div key={`${session.tipo}-${idx}`} className="group relative md:pl-10">
            <div className="absolute left-[7px] top-5 hidden h-2 w-2 rounded-full bg-primary transition-transform group-hover:scale-150 md:block" />

            <div className="rounded-2xl border border-border/60 bg-card p-4 shadow-sm transition-colors hover:border-primary/30">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <Badge
                    variant="outline"
                    className="rounded-md bg-muted/40 px-2 py-0.5 font-mono text-[10px]"
                  >
                    {session.tipo}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {new Date(session.fecha).toLocaleDateString("es-CO", {
                      weekday: "long",
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </span>
                </div>
                <CheckCircle2 className="h-4 w-4 text-muted-foreground/30" />
              </div>

              <h4 className="mb-2 text-sm font-medium">{session.titulo}</h4>
              <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-foreground/80">
                {session.descripcion.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
