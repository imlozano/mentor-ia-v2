"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StudyAssistant } from "@/components/study-assistant";
import { ReviewPlan } from "@/components/review-plan";

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
          <StudyAssistant />
        </TabsContent>
        <TabsContent value="plan" className="mt-4">
          <ReviewPlan />
        </TabsContent>
      </Tabs>
    </main>
  );
}
