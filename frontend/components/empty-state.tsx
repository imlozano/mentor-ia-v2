import { Sparkles } from "lucide-react";
import { type ReactNode } from "react";

export function EmptyState({
  title,
  subtitle,
  action,
  icon,
}: {
  title: string;
  subtitle: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-dashed border-border/50 bg-muted/10 p-8 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-muted/60 text-muted-foreground">
        {icon ?? <Sparkles className="h-6 w-6 opacity-50" />}
      </div>
      <h3 className="text-base font-medium text-foreground/80">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{subtitle}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
