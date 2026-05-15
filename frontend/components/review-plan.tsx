"use client";

import { useRef, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Calendar as CalendarIcon,
  CheckCircle2,
  Clock,
  Upload,
} from "lucide-react";

import { createPlan } from "@/lib/api";
import type { PlanRepasoResponse } from "@/lib/types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { PlanTimeline } from "@/components/plan-timeline";

type Mode = "tema" | "archivo";

export function ReviewPlan() {
  const [mode, setMode] = useState<Mode>("tema");
  const [topic, setTopic] = useState("");
  const [date, setDate] = useState("");
  const [email, setEmail] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<PlanRepasoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  function isValid() {
    if (!date) return false;
    if (mode === "tema") return topic.trim().length > 0;
    return file !== null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid()) return;
    setError(null);
    setBusy(true);
    setPlan(null);
    try {
      const res = await createPlan({
        tema: mode === "tema" ? topic.trim() : topic.trim() || (file?.name ?? "Plan"),
        fecha_inicio: date,
        email: email.trim() || undefined,
        archivo: mode === "archivo" ? file ?? undefined : undefined,
      });
      setPlan(res);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible generar el plan.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-[calc(100vh-10rem)] grid-cols-1 gap-6 lg:grid-cols-12">
      <aside className="space-y-5 lg:col-span-4">
        <div className="overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm">
          <div className="border-b border-border/60 p-5">
            <div className="mb-1 flex items-center gap-2.5">
              <CalendarIcon className="h-4 w-4 text-primary/70" />
              <h3 className="text-base font-semibold">Configurar plan</h3>
            </div>
            <p className="text-sm text-muted-foreground">
              Genera un cronograma de repaso espaciado.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5 p-5">
            <div className="space-y-2.5">
              <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Fuente del plan
              </Label>
              <RadioGroup
                value={mode}
                onValueChange={(value) => setMode(value as Mode)}
                className="grid grid-cols-2 gap-3"
              >
                <div>
                  <RadioGroupItem
                    value="tema"
                    id="mode-tema"
                    className="peer sr-only"
                  />
                  <Label
                    htmlFor="mode-tema"
                    className="flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-muted bg-background p-4 transition-all hover:bg-muted/30 peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5"
                  >
                    <BookOpen className="h-5 w-5 text-muted-foreground peer-data-[state=checked]:text-primary" />
                    <span className="text-xs font-medium">Tema</span>
                  </Label>
                </div>
                <div>
                  <RadioGroupItem
                    value="archivo"
                    id="mode-archivo"
                    className="peer sr-only"
                  />
                  <Label
                    htmlFor="mode-archivo"
                    className="flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-muted bg-background p-4 transition-all hover:bg-muted/30 peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5"
                  >
                    <Upload className="h-5 w-5 text-muted-foreground peer-data-[state=checked]:text-primary" />
                    <span className="text-xs font-medium">Archivo</span>
                  </Label>
                </div>
              </RadioGroup>
            </div>

            {mode === "tema" ? (
              <div className="space-y-2">
                <Label
                  htmlFor="topic"
                  className="text-xs font-medium uppercase tracking-wider text-muted-foreground"
                >
                  Tema de estudio
                </Label>
                <Input
                  id="topic"
                  placeholder="Ej: Algoritmos de ordenamiento"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  required
                  className="rounded-xl border-0 bg-muted/30 focus-visible:ring-1 focus-visible:ring-primary/50"
                />
              </div>
            ) : (
              <div className="space-y-2.5">
                <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Subir material
                </Label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border px-4 py-3 text-sm text-muted-foreground transition-all hover:border-primary/50 hover:bg-primary/5 hover:text-foreground"
                >
                  {file ? "Cambiar archivo" : "Seleccionar PDF / TXT / MD"}
                </button>
                {file ? (
                  <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 p-2.5 text-xs text-emerald-700 dark:text-emerald-300">
                    <CheckCircle2 className="h-4 w-4" />
                    <span className="truncate">{file.name}</span>
                  </div>
                ) : null}
                <div>
                  <Label
                    htmlFor="topic-file"
                    className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground"
                  >
                    Tema (opcional)
                  </Label>
                  <Input
                    id="topic-file"
                    placeholder="Resumen del archivo"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className="mt-1 rounded-xl border-0 bg-muted/30 focus-visible:ring-1 focus-visible:ring-primary/50"
                  />
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label
                htmlFor="date"
                className="text-xs font-medium uppercase tracking-wider text-muted-foreground"
              >
                Fecha de inicio
              </Label>
              <Input
                id="date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
                className="block w-full rounded-xl border-0 bg-muted/30 focus-visible:ring-1 focus-visible:ring-primary/50"
              />
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="email"
                className="text-xs font-medium uppercase tracking-wider text-muted-foreground"
              >
                Email para envío (opcional)
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="tu-email@ejemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-xl border-0 bg-muted/30 focus-visible:ring-1 focus-visible:ring-primary/50"
              />
              <p className="text-[11px] text-muted-foreground">
                Si lo indicas, el plan se enviará automáticamente.
              </p>
            </div>

            <Button
              type="submit"
              className="h-11 w-full rounded-xl"
              disabled={busy || !isValid()}
            >
              {busy ? "Generando plan..." : "Generar plan de repaso"}
              {!busy ? <ArrowRight className="ml-1 h-4 w-4" /> : null}
            </Button>
          </form>
        </div>

        <div className="rounded-2xl bg-muted/30 p-4 text-sm">
          <div className="mb-2 flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary/70" />
            <h4 className="font-medium">¿Cómo funciona?</h4>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Usamos <strong className="text-foreground">repaso espaciado</strong> con
            sesiones a D+1, D+7, D+14 y D+30 para maximizar retención a largo
            plazo.
          </p>
        </div>
      </aside>

      <section className="lg:col-span-8">
        {error ? (
          <Alert variant="destructive" className="mb-5">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {busy ? (
          <div className="space-y-4">
            <Skeleton className="h-28 w-full rounded-2xl" />
            <div className="mt-6 space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-20 w-full rounded-xl" />
              ))}
            </div>
          </div>
        ) : null}

        {!busy && plan ? (
          <div className="space-y-6">
            <div className="rounded-2xl border border-primary/10 bg-primary/5 p-5">
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                <div>
                  <h2 className="text-xl font-semibold tracking-tight">
                    {plan.tema}
                  </h2>
                  <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                    <CalendarIcon className="h-3.5 w-3.5" />
                    Inicio:{" "}
                    {new Date(plan.fecha_inicio).toLocaleDateString("es-CO")}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge
                    variant="secondary"
                    className="self-start rounded-full px-3 py-1 text-xs"
                  >
                    Plan generado
                  </Badge>
                  {plan.email_enviado ? (
                    <Badge
                      variant="success"
                      className="self-start rounded-full px-3 py-1 text-xs"
                    >
                      Enviado por email
                    </Badge>
                  ) : null}
                </div>
              </div>
            </div>

            <PlanTimeline sessions={plan.sesiones} />
          </div>
        ) : null}

        {!busy && !plan && !error ? (
          <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border/50 bg-muted/10 p-8 text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-muted/50">
              <BookOpen className="h-6 w-6 text-muted-foreground/40" />
            </div>
            <p className="text-base font-medium text-foreground/70">
              Planifica tu éxito
            </p>
            <p className="mt-1 max-w-xs text-sm text-muted-foreground">
              Configura un tema o sube un archivo para generar tu cronograma
              personalizado.
            </p>
          </div>
        ) : null}
      </section>
    </div>
  );
}
