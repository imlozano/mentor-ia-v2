import type { Fuente, Origen } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

type ChatMessage =
  | { role: "user"; content: string }
  | { role: "agent"; content: string; sources: Fuente[]; origen: Origen };

export function ChatMessageItem({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl bg-primary px-4 py-3 text-sm leading-relaxed text-primary-foreground shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-2xl bg-muted/60 px-4 py-3 text-sm leading-relaxed">
        <div className="mb-2">
          {message.origen === "rag" ? (
            <Badge variant="secondary" className="rounded-full text-[10px]">
              RAG · {message.sources.length} fuentes
            </Badge>
          ) : (
            <Badge variant="outline" className="rounded-full text-[10px]">
              Conocimiento general
            </Badge>
          )}
        </div>
        <p className="whitespace-pre-wrap">{message.content}</p>
        {message.origen === "rag" && message.sources.length > 0 ? (
          <details className="mt-3 text-xs text-muted-foreground">
            <summary className="cursor-pointer hover:text-foreground">
              Ver fuentes
            </summary>
            <ul className="mt-2 space-y-2 font-mono text-[11px]">
              {message.sources.map((s, idx) => (
                <li key={`${s.archivo}-${s.chunk_index}-${idx}`} className="border-l-2 border-muted-foreground/20 pl-2">
                  <div className="font-semibold">
                    {s.archivo} · chunk {s.chunk_index}
                    {s.score != null ? ` · score ${s.score.toFixed(3)}` : ""}
                  </div>
                  {s.excerpt && (
                    <div className="mt-1 font-normal text-muted-foreground leading-relaxed whitespace-pre-wrap">
                      {s.excerpt}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </div>
  );
}
