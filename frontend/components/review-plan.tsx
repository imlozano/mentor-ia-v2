"use client";

import { useState } from "react";

import { createPlan } from "@/lib/api";
import type { PlanRepasoResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { PlanTimeline } from "@/components/plan-timeline";

export function ReviewPlan() {
  const [mode, setMode] = useState<"tema" | "archivo">("tema");
  const [topic, setTopic] = useState("");
  const [date, setDate] = useState("");
  const [email, setEmail] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<PlanRepasoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      const res = await createPlan({
        tema: topic,
        fecha_inicio: date,
        email: email || undefined,
        archivo: mode === "archivo" ? (file || undefined) : undefined,
      });
      setPlan(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible generar el plan.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-4 space-y-4">
        <RadioGroup value={mode} onValueChange={(value) => setMode(value as "tema" | "archivo")}>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="tema" id="mode-tema" />
            <Label htmlFor="mode-tema">Modo Tema</Label>
          </div>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="archivo" id="mode-archivo" />
            <Label htmlFor="mode-archivo">Modo Archivo</Label>
          </div>
        </RadioGroup>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="tema">Tema</Label>
            <Input id="tema" value={topic} onChange={(e) => setTopic(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="fecha">Fecha inicio</Label>
            <Input id="fecha" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
        </div>

        <div className="space-y-1">
          <Label htmlFor="email">Email (opcional)</Label>
          <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>

        {mode === "archivo" ? (
          <div className="space-y-1">
            <Label htmlFor="archivo">Archivo</Label>
            <Input
              id="archivo"
              type="file"
              accept=".pdf,.txt,.md"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>
        ) : null}

        <Button onClick={() => void submit()} disabled={busy || !topic || !date || (mode === "archivo" && !file)}>
          Generar plan de repaso
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {plan?.email_enviado ? (
        <Alert>
          <AlertTitle>Plan enviado</AlertTitle>
          <AlertDescription>Se envio una copia del plan al correo indicado.</AlertDescription>
        </Alert>
      ) : null}

      {plan ? <PlanTimeline sessions={plan.sesiones} /> : null}
    </div>
  );
}

