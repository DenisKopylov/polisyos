import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/Badge";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AlertSeverity = "critical" | "warning" | "info";

export type ActiveAlert = {
  id: string;
  severity: AlertSeverity;
  message: string;
  source?: string;
  timestamp?: string;
};

type ActiveAlertsStripProps = {
  alerts: ActiveAlert[];
  className?: string;
  onDismiss?: (alertId: string) => void;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SEVERITY_BADGE: Record<AlertSeverity, "fail" | "warn" | "neutral"> = {
  critical: "fail",
  warning: "warn",
  info: "neutral",
};

const SEVERITY_BORDER: Record<AlertSeverity, string> = {
  critical: "var(--color-status-rejected)",
  warning: "var(--color-status-pending)",
  info: "var(--line)",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ActiveAlertsStrip({
  alerts,
  className,
  onDismiss,
}: ActiveAlertsStripProps) {
  if (alerts.length === 0) return null;

  return (
    <div className={cn("space-y-1.5", className)}>
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className="border-line bg-surface flex items-center gap-3 rounded-xl border p-2.5 text-xs"
          style={{
            borderLeftWidth: 3,
            borderLeftColor: SEVERITY_BORDER[alert.severity],
          }}
        >
          <Badge kind={SEVERITY_BADGE[alert.severity]}>{alert.severity}</Badge>
          <p className="flex-1 truncate">{alert.message}</p>
          {alert.source && (
            <span className="text-muted shrink-0">{alert.source}</span>
          )}
          {onDismiss && (
            <button
              type="button"
              className="text-muted hover:text-foreground shrink-0 text-xs"
              onClick={() => onDismiss(alert.id)}
              aria-label={`Dismiss alert: ${alert.message}`}
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
