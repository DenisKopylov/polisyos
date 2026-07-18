import { useRuns } from "@/api/hooks/useRuns";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatDate } from "@/shared/lib/utils";
import { Badge, Button, Card } from "@polisyos/atlas-ui";

function statusToBadgeKind(status: string | undefined) {
  if (!status) return "neutral" as const;
  if (status === "completed") return "ok" as const;
  if (status === "failed" || status === "error") return "fail" as const;
  if (status === "running" || status === "pending") return "info" as const;
  return "neutral" as const;
}

export function ClerkHistoryList() {
  const { label, locale, t } = useI18n();
  const runsQuery = useRuns({ limit: 20 });

  if (runsQuery.isLoading) {
    return (
      <Card className="p-8">
        <p className="text-[var(--slate)]">{t("common.loading")}</p>
      </Card>
    );
  }

  const runs = runsQuery.data?.runs ?? [];

  if (runs.length === 0) {
    return (
      <div className="mx-auto flex max-w-[860px] flex-col items-center gap-4 pt-16 text-center">
        <h2 className="text-lg font-bold text-[var(--ink)]">
          {t("clerk.myAnalyses")}
        </h2>
        <p className="text-sm text-[var(--slate)]">
          {t("clerk.welcomeSubtitle")}
        </p>
        <Button variant="primary" to="/">
          {t("clerk.newAnalysis")}
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[860px] flex-col gap-4">
      <h2 className="text-lg font-bold text-[var(--ink)]">
        {t("clerk.myAnalyses")}
      </h2>
      {runs.map((run) => (
        <Card key={run.run_id} className="p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Badge kind={statusToBadgeKind(run.status)}>
                {label(
                  "runStatuses",
                  run.status,
                  run.status ?? t("common.unknown"),
                )}
              </Badge>
              <span className="text-sm font-semibold text-[var(--ink)]">
                {run.run_id.slice(0, 12)}...
              </span>
              <span className="text-xs text-[var(--slate)]">
                {run.started_at ? formatDate(run.started_at, locale) : ""}
              </span>
            </div>
            <Button variant="ghost" size="sm" to={`/runs/${run.run_id}`}>
              {t("clerk.viewFullAnalysis")}
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
