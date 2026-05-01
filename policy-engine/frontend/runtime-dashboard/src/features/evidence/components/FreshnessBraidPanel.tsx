import type {
  FreshnessBraidView,
  FreshnessState,
} from "../domain/productionSlice";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn, formatDate, formatDuration, formatNumber } from "@/lib/utils";
import { Badge, Card, EmptyState } from "@/shared/ui";

function stateKind(state: FreshnessState) {
  if (state === "ok") return "ok";
  if (state === "warn") return "warn";
  if (state === "fail") return "fail";
  return "neutral";
}

function threadColor(state: FreshnessState) {
  if (state === "ok") return "bg-[var(--color-status-approved)]";
  if (state === "warn") return "bg-[var(--color-status-pending)]";
  if (state === "fail") return "bg-[var(--color-status-rejected)]";
  return "bg-muted";
}

export function FreshnessBraidPanel({ view }: { view: FreshnessBraidView }) {
  const { t } = useI18n();

  if (view.threads.length === 0) {
    return (
      <Card data-testid="freshness-braid-panel">
        <EmptyState
          title={t("phase32.freshness.emptyTitle")}
          body={t("phase32.freshness.emptyBody")}
        />
      </Card>
    );
  }

  return (
    <Card className="space-y-4" data-testid="freshness-braid-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("phase32.freshness.eyebrow")}</p>
          <h3>{t("phase32.freshness.title")}</h3>
          <p className="topbar-subtitle mt-2">{t("phase32.freshness.body")}</p>
        </div>
        <Badge kind={view.governingLagMs === null ? "neutral" : "warn"}>
          {t("phase32.freshness.governingLag", {
            lag: formatDuration(view.governingLagMs),
          })}
        </Badge>
      </div>

      <div className="space-y-3" role="list">
        {view.threads.map((thread) => (
          <div
            key={thread.connectorId}
            className={cn(
              "border-line bg-surface/80 grid gap-3 rounded-2xl border p-3 md:grid-cols-[minmax(12rem,0.9fr)_minmax(0,1fr)_auto]",
              thread.governing && "border-warning/50 bg-warning/5",
            )}
            role="listitem"
          >
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <strong>{thread.label}</strong>
                <Badge kind={stateKind(thread.state)}>{thread.state}</Badge>
                {thread.governing ? (
                  <Badge kind="warn">{t("phase32.freshness.governing")}</Badge>
                ) : null}
              </div>
              <p className="text-muted mt-1 text-xs">
                {thread.lastObservedAt
                  ? formatDate(thread.lastObservedAt)
                  : t("common.unavailable")}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="bg-line h-3 flex-1 overflow-hidden rounded-full">
                <div
                  className={cn(
                    "h-full rounded-full",
                    threadColor(thread.state),
                  )}
                  style={{
                    width: `${Math.max(
                      8,
                      Math.min(100, 18 + thread.volume * 4),
                    )}%`,
                  }}
                />
              </div>
              <span className="text-muted min-w-20 text-right font-mono text-xs">
                {formatDuration(thread.lagMs)}
              </span>
            </div>
            <div className="text-right text-xs">
              <p className="font-semibold">
                {t("phase32.freshness.volume", {
                  value: formatNumber(thread.volume),
                })}
              </p>
              <p className="text-muted">
                {t("phase32.freshness.derivedFacts", {
                  value: formatNumber(thread.derivedFactCount),
                })}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="border-line bg-surface/70 rounded-2xl border p-3">
        <p className="text-muted text-xs font-semibold tracking-wide uppercase">
          {t("phase32.freshness.joinNodes")}
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {view.joinNodes.map((join) => (
            <Badge key={join.id} kind="outline">
              {join.label} · {formatNumber(join.sourceCount)}
            </Badge>
          ))}
        </div>
      </div>
    </Card>
  );
}
