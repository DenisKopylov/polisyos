import type { FreshnessBraidView } from "../domain/productionSlice";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatDate, formatDuration, formatNumber } from "@/shared/lib/utils";
import { Badge, Card, EmptyState } from "@polisyos/atlas-ui";

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
        <span className="text-muted text-xs">
          {t("phase32.freshness.governingLag", {
            lag: formatDuration(view.governingLagMs),
          })}
        </span>
      </div>

      <div className="space-y-3" role="list">
        {view.threads.map((thread) => (
          <div
            key={thread.connectorId}
            className="border-line bg-surface/80 grid gap-3 rounded-2xl border p-3 md:grid-cols-[minmax(12rem,0.9fr)_minmax(0,1fr)_auto]"
            data-display-state={thread.state.label}
            data-interaction-purpose={thread.state.authorityPurpose}
            role="listitem"
          >
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <strong>{thread.label}</strong>
                <span className="text-muted text-xs">
                  {thread.state.label}
                </span>
                {thread.governing ? (
                  <span className="text-muted text-xs">
                    {t("phase32.freshness.governing")}
                  </span>
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
                  aria-hidden="true"
                  className="bg-muted h-full rounded-full"
                  data-testid={`freshness-thread-fill-${thread.connectorId}`}
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
