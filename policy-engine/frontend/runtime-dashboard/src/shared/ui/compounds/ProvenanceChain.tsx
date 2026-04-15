import { cn } from "@/lib/utils";
import { Badge, Button, Card } from "@/shared/ui/primitives";
import type { BadgeKind } from "@/shared/ui/Badge";

export type ProvenanceStep = {
  id: string;
  label: string;
  type: "data" | "method" | "result" | "governance";
  detail?: string;
  status?: BadgeKind;
  statusLabel?: string;
  href?: string;
  timestamp?: string;
};

type ProvenanceChainProps = {
  steps: ProvenanceStep[];
  title?: string;
  className?: string;
};

const TYPE_ICON: Record<ProvenanceStep["type"], string> = {
  data: "\uD83D\uDDC3",
  method: "\u2699",
  result: "\uD83D\uDCCA",
  governance: "\uD83D\uDEE1",
};

const TYPE_COLOR: Record<ProvenanceStep["type"], string> = {
  data: "border-[var(--color-transport-live)]",
  method: "border-[var(--color-status-pending)]",
  result: "border-[var(--color-status-approved)]",
  governance: "border-[var(--color-governance-review)]",
};

export function ProvenanceChain({
  steps,
  title = "Provenance",
  className,
}: ProvenanceChainProps) {
  return (
    <Card className={cn("space-y-3", className)}>
      <h3 className="text-lg font-semibold">{title}</h3>
      <div className="relative">
        {steps.map((step, i) => (
          <div key={step.id} className="flex gap-3">
            {/* Vertical connector */}
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 bg-[var(--panel)] text-sm",
                  TYPE_COLOR[step.type],
                )}
                aria-hidden="true"
              >
                {TYPE_ICON[step.type]}
              </div>
              {i < steps.length - 1 && (
                <div className="bg-line w-0.5 flex-1" />
              )}
            </div>

            {/* Content */}
            <div className={cn("pb-5", i === steps.length - 1 && "pb-0")}>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold">{step.label}</p>
                {step.status && step.statusLabel && (
                  <Badge kind={step.status}>{step.statusLabel}</Badge>
                )}
                <span className="text-muted text-xs uppercase tracking-wide">
                  {step.type}
                </span>
              </div>
              {step.detail && (
                <p className="text-muted mt-1 text-sm">{step.detail}</p>
              )}
              <div className="mt-1 flex items-center gap-2">
                {step.timestamp && (
                  <span className="text-muted font-mono text-xs">
                    {step.timestamp}
                  </span>
                )}
                {step.href && (
                  <Button href={step.href} size="sm" variant="link">
                    View
                  </Button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
