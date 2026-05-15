import type { Fuente, Origen } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

type ChatMessage =
  | { role: "user"; content: string }
  | { role: "agent"; content: string; sources: Fuente[]; origen: Origen };

export function ChatMessageItem({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-lg bg-muted px-3 py-2 text-sm">
        <div className="mb-2">
          {message.origen === "rag" ? (
            <Badge variant="secondary">RAG · {message.sources.length} fuentes</Badge>
          ) : (
            <Badge variant="secondary">Conocimiento general</Badge>
          )}
        </div>
        <p className="whitespace-pre-wrap">{message.content}</p>
        {message.origen === "rag" && message.sources.length > 0 ? (
          <details className="mt-2 text-xs text-muted-foreground">
            <summary>Ver fuentes</summary>
            <ul className="mt-1 space-y-1">
              {message.sources.map((s, idx) => (
                <li key={`${s.archivo}-${s.chunk_index}-${idx}`}>
                  {s.archivo} · chunk {s.chunk_index}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </div>
  );
}

