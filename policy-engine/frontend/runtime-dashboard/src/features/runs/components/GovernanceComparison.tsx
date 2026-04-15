import { cn } from "@/lib/utils";
import { Card } from "@/shared/ui/primitives";
import { Badge } from "@/shared/ui/Badge";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GovernanceComparisonItem = {
  passId: string;
  label: string;
  baseStatus: "pass" | "fail" | "warning" | "skip";
  targetStatus: "pass" | "fail" | "warning" | "skip";
};

type GovernanceComparisonProps = {
  items: GovernanceComparisonItem[];
  baseLabel?: string;
  targetLabel?: string;
  className?: string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_BADGE_KIND: Record<string, "ok" | "fail" | "warn" | "neutral"> = {
  pass: "ok",
  fail: "fail",
  warning: "warn",
  skip: "neutral",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GovernanceComparison({
  items,
  baseLabel = "Base",
  targetLabel = "Target",
  className,
}: GovernanceComparisonProps) {
  const changed = items.filter((i) => i.baseStatus !== i.targetStatus);
  const unchanged = items.filter((i) => i.baseStatus === i.targetStatus);

  return (
    <Card className={cn("space-y-3 p-4", className)}>
      <h4 className="text-sm font-semibold">Governance Comparison</h4>

      {items.length === 0 ? (
        <p className="text-muted text-xs">No governance passes to compare.</p>
      ) : (
        <>
          {/* Table header */}
          <div className="text-muted grid grid-cols-3 gap-2 text-xs font-semibold">
            <span>Pass</span>
            <span className="text-center">{baseLabel}</span>
            <span className="text-center">{targetLabel}</span>
          </div>

          {/* Changed first */}
          {changed.map((item) => (
            <div
              key={item.passId}
              className="border-line grid grid-cols-3 items-center gap-2 rounded-lg border p-2"
              style={{ borderLeftWidth: 3, borderLeftColor: "var(--chart-warning)" }}
            >
              <span className="text-xs font-medium">{item.label}</span>
              <span className="text-center">
                <Badge kind={STATUS_BADGE_KIND[item.baseStatus] ?? "neutral"}>
                  {item.baseStatus}
                </Badge>
              </span>
              <span className="text-center">
                <Badge kind={STATUS_BADGE_KIND[item.targetStatus] ?? "neutral"}>
                  {item.targetStatus}
                </Badge>
              </span>
            </div>
          ))}

          {/* Unchanged */}
          {unchanged.length > 0 && (
            <details className="text-xs">
              <summary className="text-muted cursor-pointer">
                {unchanged.length} unchanged passes
              </summary>
              <div className="mt-1.5 space-y-1">
                {unchanged.map((item) => (
                  <div
                    key={item.passId}
                    className="text-muted grid grid-cols-3 items-center gap-2 px-2 py-1"
                  >
                    <span>{item.label}</span>
                    <span className="text-center">
                      <Badge kind={STATUS_BADGE_KIND[item.baseStatus] ?? "neutral"}>
                        {item.baseStatus}
                      </Badge>
                    </span>
                    <span className="text-center">—</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </Card>
  );
}
