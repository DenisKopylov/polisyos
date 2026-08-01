import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  createInteractionState,
  type InteractionState,
} from "@/shared/lib/domain/statusOwnership";
import { cn } from "@/shared/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SystemHealthDisplayState = InteractionState;

export function createSystemHealthDisplayState(
  label: string,
): SystemHealthDisplayState {
  return createInteractionState(label, "telemetry");
}

export type HealthCheck = {
  id: string;
  label: string;
  status: SystemHealthDisplayState;
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

function statusColor(status: SystemHealthDisplayState) {
  if (status.label === "healthy") return "var(--color-status-approved)";
  if (status.label === "degraded") return "var(--color-status-pending)";
  if (status.label === "down") return "var(--color-status-rejected)";
  return "var(--line)";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SystemHealthPulse({
  checks,
  className,
}: SystemHealthPulseProps) {
  const { t } = useI18n();
  const statusLabel = (status: SystemHealthDisplayState) => {
    if (status.label === "healthy") {
      return t("features.dashboard.systemHealth.status.healthy");
    }
    if (status.label === "degraded") {
      return t("features.dashboard.systemHealth.status.degraded");
    }
    if (status.label === "down") {
      return t("features.dashboard.systemHealth.status.down");
    }
    return t("features.dashboard.systemHealth.status.unknown");
  };
  const overallStatus = createSystemHealthDisplayState(
    checks.some((c) => c.status.label === "down")
      ? "down"
      : checks.some((c) => c.status.label === "degraded")
        ? "degraded"
        : checks.every((c) => c.status.label === "healthy")
          ? "healthy"
          : "unknown",
  );

  return (
    <div className={cn("space-y-3", className)}>
      {/* Overall pulse */}
      <div className="flex items-center gap-2">
        <span
          className="relative flex size-3"
          data-authority-purpose={overallStatus.authorityPurpose}
          data-testid="system-health-overall"
          aria-label={t("features.dashboard.systemHealth.aria", {
            status: statusLabel(overallStatus),
          })}
        >
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-40"
            style={{ background: statusColor(overallStatus) }}
          />
          <span
            className="relative inline-flex size-3 rounded-full"
            style={{ background: statusColor(overallStatus) }}
          />
        </span>
        <span className="text-sm font-semibold">
          {t("features.dashboard.systemHealth.summary", {
            status: statusLabel(overallStatus),
          })}
        </span>
      </div>

      {/* Individual checks grid */}
      <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {checks.map((check) => (
          <div
            aria-label={check.label}
            key={check.id}
            className="border-line flex items-center gap-2 rounded-lg border p-2 text-xs"
            data-authority-purpose={check.status.authorityPurpose}
            data-health-state={check.status.label}
            role="group"
          >
            <span
              className="size-2 shrink-0 rounded-full"
              style={{ background: statusColor(check.status) }}
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
