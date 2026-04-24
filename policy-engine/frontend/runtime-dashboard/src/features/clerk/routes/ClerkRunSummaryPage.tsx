import { useParams } from "react-router-dom";

import { useRunDetails } from "@/api/hooks/useRunDetails";
import { useI18n } from "@/i18n/LocaleProvider";
import { formatDate, formatDuration } from "@/lib/utils";
import { Badge, Button, Card } from "@/shared/ui";

function statusToBadgeKind(status: string | undefined) {
  if (!status) return "neutral" as const;
  if (status === "completed") return "ok" as const;
  if (status === "failed" || status === "error") return "fail" as const;
  if (status === "running" || status === "pending") return "info" as const;
  return "neutral" as const;
}

export default function ClerkRunSummaryPage() {
  const { label, locale, t } = useI18n();
  const { runId } = useParams<{ runId: string }>();
  const runQuery = useRunDetails(runId ?? "");

  if (runQuery.isLoading) {
    return (
      <Card className="p-8">
        <p className="text-[var(--slate)]">{t("common.loading")}</p>
      </Card>
    );
  }

  if (runQuery.isError || !runQuery.data) {
    return (
      <Card className="p-8">
        <p className="text-[var(--danger)]">{t("common.requestFailed")}</p>
      </Card>
    );
  }

  const { run } = runQuery.data;

  return (
    <div className="mx-auto flex max-w-[860px] flex-col gap-6">
      <Card className="p-8">
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <Badge kind={statusToBadgeKind(run.status)}>
              {label(
                "runStatuses",
                run.status,
                run.status ?? t("common.unknown"),
              )}
            </Badge>
          </div>

          <h2 className="text-xl font-bold text-[var(--ink)]">{run.run_id}</h2>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-[var(--slate)]">{t("clerk.started")}</span>
              <p className="font-semibold text-[var(--ink)]">
                {run.started_at ? formatDate(run.started_at, locale) : "-"}
              </p>
            </div>
            <div>
              <span className="text-[var(--slate)]">{t("clerk.duration")}</span>
              <p className="font-semibold text-[var(--ink)]">
                {formatDuration(run.duration_ms, locale)}
              </p>
            </div>
          </div>
        </div>
      </Card>

      <div className="flex gap-3">
        <Button variant="ghost" size="sm" to="/">
          {t("clerk.returnToChat")}
        </Button>
      </div>
    </div>
  );
}
