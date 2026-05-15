import { type ReactNode } from "react";

export function EmptyState({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border p-6 text-center">
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

