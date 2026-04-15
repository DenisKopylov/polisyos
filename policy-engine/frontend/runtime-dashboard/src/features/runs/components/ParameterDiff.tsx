import { useMemo } from "react";

import { cn } from "@/lib/utils";
import { Card } from "@/shared/ui/primitives";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ParameterDiffEntry = {
  key: string;
  label: string;
  base: string | number | boolean | null;
  target: string | number | boolean | null;
};

type ParameterDiffProps = {
  parameters: ParameterDiffEntry[];
  className?: string;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ParameterDiff({ parameters, className }: ParameterDiffProps) {
  const { changed, unchanged } = useMemo(() => {
    const c: ParameterDiffEntry[] = [];
    const u: ParameterDiffEntry[] = [];
    for (const p of parameters) {
      if (String(p.base) !== String(p.target)) {
        c.push(p);
      } else {
        u.push(p);
      }
    }
    return { changed: c, unchanged: u };
  }, [parameters]);

  return (
    <Card className={cn("space-y-3 p-4", className)}>
      <h4 className="text-sm font-semibold">Parameter Differences</h4>

      {changed.length === 0 ? (
        <p className="text-muted text-xs">All parameters are identical.</p>
      ) : (
        <div className="space-y-1.5">
          {changed.map((p) => (
            <div
              key={p.key}
              className="border-line flex items-baseline justify-between gap-3 rounded-lg border p-2 text-xs"
              style={{ borderLeftWidth: 3, borderLeftColor: "var(--chart-warning)" }}
            >
              <span className="font-semibold">{p.label}</span>
              <div className="flex gap-2">
                <span className="text-[var(--chart-alert)] line-through">
                  {String(p.base ?? "—")}
                </span>
                <span>→</span>
                <span className="text-[var(--chart-success)]">
                  {String(p.target ?? "—")}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {unchanged.length > 0 && (
        <details className="text-xs">
          <summary className="text-muted cursor-pointer">
            {unchanged.length} unchanged parameters
          </summary>
          <div className="mt-1.5 space-y-1">
            {unchanged.map((p) => (
              <div
                key={p.key}
                className="text-muted flex justify-between rounded-md px-2 py-1"
              >
                <span>{p.label}</span>
                <span className="font-mono">{String(p.base ?? "—")}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </Card>
  );
}
