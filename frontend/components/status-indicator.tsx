"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

type HealthState = "checking" | "online" | "partial" | "offline";

const LABELS: Record<HealthState, string> = {
  checking: "Verificando",
  online: "Online",
  partial: "Parcial",
  offline: "Offline",
};

const DOT_COLORS: Record<HealthState, string> = {
  checking: "bg-muted-foreground",
  online: "bg-emerald-500",
  partial: "bg-amber-500",
  offline: "bg-destructive",
};

const PING_COLORS: Record<HealthState, string> = {
  checking: "bg-muted-foreground/50",
  online: "bg-emerald-400",
  partial: "bg-amber-400",
  offline: "bg-destructive/60",
};

export function StatusIndicator() {
  const [state, setState] = useState<HealthState>("checking");

  useEffect(() => {
    let mounted = true;

    const run = async () => {
      try {
        const health = await getHealth();
        if (!mounted) return;
        const allOk = health.qdrant_ok && health.openai_ok;
        setState(allOk ? "online" : "partial");
      } catch {
        if (!mounted) return;
        setState("offline");
      }
    };

    void run();
    const id = setInterval(() => void run(), 30_000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="flex items-center gap-2">
      <span className="relative flex h-2 w-2">
        {state !== "checking" ? (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              PING_COLORS[state],
            )}
          />
        ) : null}
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            DOT_COLORS[state],
          )}
        />
      </span>
      <span className="text-xs font-medium text-muted-foreground">
        {LABELS[state]}
      </span>
    </div>
  );
}
