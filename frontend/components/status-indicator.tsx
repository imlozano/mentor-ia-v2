"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

type HealthState = "checking" | "online" | "partial" | "offline";

export function StatusIndicator() {
  const [state, setState] = useState<HealthState>("checking");

  useEffect(() => {
    let mounted = true;

    const run = async () => {
      try {
        const health = await getHealth();
        if (!mounted) return;
        if (health.qdrant_ok && health.gemini_ok) setState("online");
        else setState("partial");
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

  if (state === "checking") return <Badge variant="secondary">Verificando...</Badge>;
  if (state === "online") return <Badge className="bg-green-600 hover:bg-green-600">Online</Badge>;
  if (state === "partial") return <Badge className="bg-yellow-500 hover:bg-yellow-500">Parcial</Badge>;
  return <Badge variant="destructive">Offline</Badge>;
}

