import type { RunChoreographyView } from "@/features/runs/domain/runChoreography";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  cn,
  formatDate,
  formatDuration,
  formatNumber,
} from "@/shared/lib/utils";
import { Badge, EmptyState } from "@polisyos/atlas-ui";

function statusKind(status: RunChoreographyView["lanes"][number]["status"]) {
  if (status === "complete") return "ok";
  if (status === "blocked") return "fail";
  if (status === "running") return "warn";
  return "neutral";
}

export function RunChoreographyPanel({ view }: { view: RunChoreographyView }) {
  const { t } = useI18n();

  if (view.lanes.length === 0) {
    return (
      <EmptyState
        title={t("phase32.choreography.emptyTitle")}
        body={t("phase32.choreography.emptyBody")}
      />
    );
  }

  return (
    <div className="space-y-4" data-testid="run-choreography-panel">
      <div className="grid gap-3 md:grid-cols-3">
        <div className="compact-metric">
          <span>{t("phase32.choreography.events")}</span>
          <strong>{formatNumber(view.totalEvents)}</strong>
        </div>
        <div className="compact-metric">
          <span>{t("phase32.choreography.retries")}</span>
          <strong>{formatNumber(view.totalRetries)}</strong>
        </div>
        <div className="compact-metric">
          <span>{t("phase32.choreography.criticalPath")}</span>
          <strong>{formatDuration(view.criticalPathMs)}</strong>
        </div>
      </div>

      <div className="space-y-3">
        {view.lanes.map((lane) => (
          <section
            key={lane.id}
            className="border-line bg-surface/80 rounded-2xl border p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold">{lane.id}</p>
                <p className="text-muted text-xs">
                  {t("phase32.choreography.laneMeta", {
                    duration: formatDuration(lane.durationMs),
                    events: formatNumber(lane.events.length),
                  })}
                </p>
              </div>
              <Badge kind={statusKind(lane.status)}>{lane.status}</Badge>
            </div>

            {lane.events.length > 0 ? (
              <div className="mt-3 grid gap-2">
                {lane.events.slice(0, 5).map((event) => (
                  <div
                    key={event.id}
                    className={cn(
                      "grid gap-2 rounded-xl border px-3 py-2 text-sm md:grid-cols-[minmax(0,1fr)_auto_auto]",
                      event.status === "blocked"
                        ? "border-danger/30 bg-danger/10"
                        : "border-line bg-panel/60",
                    )}
                  >
                    <span className="flex min-w-0 flex-wrap items-center gap-2 font-medium">
                      <span className="truncate">{event.label}</span>
                      {event.retry ? (
                        <Badge kind="warn">
                          {t("phase32.choreography.retry")}
                        </Badge>
                      ) : null}
                      {event.branch ? (
                        <Badge kind="outline">
                          {t("phase32.choreography.branch")}
                        </Badge>
                      ) : null}
                    </span>
                    <span className="text-muted font-mono text-xs">
                      {formatDate(event.at)}
                    </span>
                    <span className="text-muted flex flex-wrap justify-end gap-2 text-xs">
                      <span>{formatDuration(event.durationMs)}</span>
                      {event.artifactCount > 0 ? (
                        <span>
                          {t("phase32.choreography.artifacts", {
                            value: formatNumber(event.artifactCount),
                          })}
                        </span>
                      ) : null}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted mt-3 text-sm">
                {t("phase32.choreography.noLaneEvents")}
              </p>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
