import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Parsea "YYYY-MM-DD" como fecha local. `new Date(iso)` lo interpreta como UTC,
// lo que en zonas con offset negativo (Colombia UTC-5) muestra el día anterior.
export function formatLocalDate(
  iso: string,
  opts: Intl.DateTimeFormatOptions = {},
  locale = "es-CO",
): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString(locale, opts);
}

