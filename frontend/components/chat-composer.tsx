"use client";

import { useState } from "react";
import { Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function ChatComposer({
  onSend,
  disabled = false,
}: {
  onSend: (text: string) => Promise<void> | void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");

  async function submit() {
    const value = text.trim();
    if (!value) return;
    setText("");
    await onSend(value);
  }

  return (
    <div className="space-y-1.5 pb-[env(safe-area-inset-bottom)]">
      <div className="relative">
        <Textarea
          placeholder="Escribe tu pregunta aquí..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
          disabled={disabled}
          className="max-h-[160px] min-h-[52px] resize-none rounded-xl border-0 bg-muted/40 pr-12 text-sm focus-visible:ring-1 focus-visible:ring-primary/50"
        />
        <Button
          size="icon"
          className="absolute bottom-2 right-2 h-8 w-8 rounded-lg"
          onClick={() => void submit()}
          disabled={disabled || !text.trim()}
          aria-label="Enviar pregunta"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
      <p className="text-center text-[10px] text-muted-foreground">
        El mentor puede cometer errores. Verifica la información importante.
      </p>
    </div>
  );
}
