"use client";

import { useState } from "react";
import { Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
    <div className="flex gap-2 pb-[env(safe-area-inset-bottom)]">
      <Input
        placeholder="Escribe tu pregunta..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void submit();
          }
        }}
        disabled={disabled}
      />
      <Button onClick={() => void submit()} disabled={disabled}>
        <Send className="mr-1 size-4" />
        Enviar
      </Button>
    </div>
  );
}

