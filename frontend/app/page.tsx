"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function Home() {
  return (
    <main className="mx-auto max-w-7xl p-4 md:p-6">
      <header className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-xl font-bold">Mentor IA</h1>
          <p className="text-sm text-muted-foreground">Asistente inteligente de aprendizaje</p>
        </div>
      </header>

      <Tabs defaultValue="asistente" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="asistente">Asistente de Estudio</TabsTrigger>
          <TabsTrigger value="plan">Plan de Repaso</TabsTrigger>
        </TabsList>
        <TabsContent value="asistente" className="mt-4">
          <div className="rounded-lg border p-4 text-sm text-muted-foreground">
            Contenido de Asistente de Estudio pendiente (Fase 9).
          </div>
        </TabsContent>
        <TabsContent value="plan" className="mt-4">
          <div className="rounded-lg border p-4 text-sm text-muted-foreground">
            Contenido de Plan de Repaso pendiente (Fase 10).
          </div>
        </TabsContent>
      </Tabs>
    </main>
  );
}
