"use client";

import { Brain } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StudyAssistant } from "@/components/study-assistant";
import { ReviewPlan } from "@/components/review-plan";
import { StatusIndicator } from "@/components/status-indicator";

export default function Home() {
  return (
    <div className="min-h-screen w-full bg-background">
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
              <Brain className="h-4 w-4 text-primary" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-base font-semibold leading-none tracking-tight text-foreground">
                Mentor IA
              </h1>
              <p className="mt-0.5 hidden text-[11px] leading-none text-muted-foreground sm:block">
                Asistente inteligente de aprendizaje
              </p>
            </div>
          </div>
          <StatusIndicator />
        </div>
      </header>

      <main className="w-full">
        <Tabs defaultValue="asistente" className="w-full">
          <div className="sticky top-14 z-40 w-full bg-background/80 backdrop-blur-xl">
            <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
              <div className="flex items-center justify-center">
                <TabsList>
                  <TabsTrigger value="asistente">Asistente de Estudio</TabsTrigger>
                  <TabsTrigger value="plan">Plan de Repaso</TabsTrigger>
                </TabsList>
              </div>
            </div>
          </div>

          <div className="mx-auto max-w-7xl px-4 pb-10 sm:px-6 lg:px-8">
            <TabsContent value="asistente" className="mt-0 outline-none">
              <StudyAssistant />
            </TabsContent>
            <TabsContent value="plan" className="mt-0 outline-none">
              <ReviewPlan />
            </TabsContent>
          </div>
        </Tabs>
      </main>
    </div>
  );
}
