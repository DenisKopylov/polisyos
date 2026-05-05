import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type HealthCheckStatus = "healthy" | "degraded" | "down" | "unknown";

export type HealthCheck = {
  id: string;
  label: string;
  status: HealthCheckStatus;
  latencyMs?: number;
  lastChecked?: string;
  detail?: string;
};

type SystemHealthPulseProps = {
  checks: HealthCheck[];
  className?: string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_COLOR: Record<HealthCheckStatus, string> = {
  healthy: "var(--color-status-approved)",
  degraded: "var(--color-status-pending)",
  down: "var(--color-status-rejected)",
  unknown: "var(--line)",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SystemHealthPulse({
  checks,
  className,
}: SystemHealthPulseProps) {
  const { t } = useI18n();
  const statusLabel: Record<HealthCheckStatus, string> = {
    healthy: t("features.dashboard.systemHealth.status.healthy"),
    degraded: t("features.dashboard.systemHealth.status.degraded"),
    down: t("features.dashboard.systemHealth.status.down"),
    unknown: t("features.dashboard.systemHealth.status.unknown"),
  };
  const overallStatus: HealthCheckStatus = checks.some(
    (c) => c.status === "down",
  )
    ? "down"
    : checks.some((c) => c.status === "degraded")
      ? "degraded"
      : checks.every((c) => c.status === "healthy")
        ? "healthy"
        : "unknown";

  return (
    <div className={cn("space-y-3", className)}>
      {/* Overall pulse */}
      <div className="flex items-center gap-2">
        <span
          className="relative flex size-3"
          aria-label={t("features.dashboard.systemHealth.aria", {
            status: statusLabel[overallStatus],
          })}
        >
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-40"
            style={{ background: STATUS_COLOR[overallStatus] }}
          />
          <span
            className="relative inline-flex size-3 rounded-full"
            style={{ background: STATUS_COLOR[overallStatus] }}
          />
        </span>
        <span className="text-sm font-semibold">
          {t("features.dashboard.systemHealth.summary", {
            status: statusLabel[overallStatus],
          })}
        </span>
      </div>

      {/* Individual checks grid */}
      <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {checks.map((check) => (
          <div
            key={check.id}
            className="border-line flex items-center gap-2 rounded-lg border p-2 text-xs"
          >
            <span
              className="size-2 shrink-0 rounded-full"
              style={{ background: STATUS_COLOR[check.status] }}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{check.label}</p>
              {check.detail && (
                <p className="text-muted truncate">{check.detail}</p>
              )}
            </div>
            {check.latencyMs != null && (
              <span className="text-muted shrink-0 font-mono">
                {t("features.dashboard.systemHealth.latencyMs", {
                  latency: check.latencyMs,
                })}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
