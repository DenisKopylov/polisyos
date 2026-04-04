import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { PrefetchButton } from "@/app/routes/PrefetchButton";
import { PrefetchLink } from "@/app/routes/PrefetchLink";
import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { useI18n } from "@/i18n/LocaleProvider";
import { parseRunCompareSearchParams } from "@/features/runs/domain/searchParams";
import { buildRunComparison } from "@/features/runs/domain/compare";
import { useRunDetailSummary } from "@/features/runs/routes/useRunDetailSummary";
import {
  AsyncSection,
  Button,
  Card,
  copyShareLink,
  DataTable,
  EmptyState,
  exportCsv,
  exportJson,
} from "@/shared/ui";

export default function RunComparePage() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const { base: baseRunId, target: targetRunId } =
    parseRunCompareSearchParams(searchParams);
  const baseSummary = useRunDetailSummary(baseRunId, t);
  const targetSummary = useRunDetailSummary(targetRunId, t);

  useTelemetryReadyMark("runs.compare.page", { routeId: "runs.compare" });

  const comparisonRows = useMemo(() => {
    if (!baseSummary.run || !targetSummary.run) {
      return [];
    }
    return buildRunComparison(baseSummary, targetSummary);
  }, [baseSummary, targetSummary]);
  const comparisonColumns = useMemo(
    () => [
      {
        key: "label",
        header: t("pages.runs.compare.columns.metric"),
        exportValue: (row: (typeof comparisonRows)[number]) => row.label,
        render: (row: (typeof comparisonRows)[number]) => row.label,
      },
      {
        key: "base",
        header: t("pages.runs.compare.columns.base"),
        exportValue: (row: (typeof comparisonRows)[number]) => row.base,
        render: (row: (typeof comparisonRows)[number]) => row.base,
      },
      {
        key: "target",
        header: t("pages.runs.compare.columns.target"),
        exportValue: (row: (typeof comparisonRows)[number]) => row.target,
        render: (row: (typeof comparisonRows)[number]) => row.target,
      },
      {
        key: "delta",
        header: t("pages.runs.compare.columns.delta"),
        exportValue: (row: (typeof comparisonRows)[number]) => row.delta,
        render: (row: (typeof comparisonRows)[number]) => row.delta,
      },
    ],
    [comparisonRows, t],
  );

  const isLoading =
    baseSummary.runDetailsQuery.isLoading ||
    targetSummary.runDetailsQuery.isLoading;
  const isError =
    baseSummary.runDetailsQuery.isError ||
    targetSummary.runDetailsQuery.isError;
  const error =
    baseSummary.runDetailsQuery.error ?? targetSummary.runDetailsQuery.error;

  if (!baseRunId || !targetRunId) {
    return (
      <Card>
        <EmptyState
          title={t("pages.runs.compare.requiredTitle")}
          body={t("pages.runs.compare.requiredBody")}
        />
      </Card>
    );
  }

  return (
    <div className="space-y-5" data-testid="run-compare-page">
      <Card className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{t("pages.runs.compare.eyebrow")}</p>
            <h3>{t("pages.runs.compare.title", { baseRunId, targetRunId })}</h3>
            <p className="topbar-subtitle">
              {t("pages.runs.compare.subtitle")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <PrefetchButton
              to={`/runs/${baseRunId}/report`}
              prefetch="intent"
              variant="ghost"
            >
              {t("pages.runs.compare.baseReport")}
            </PrefetchButton>
            <PrefetchButton
              to={`/runs/${targetRunId}/report`}
              prefetch="intent"
              variant="ghost"
            >
              {t("pages.runs.compare.targetReport")}
            </PrefetchButton>
            <Button
              type="button"
              onClick={() =>
                void copyShareLink(
                  new URL(
                    window.location.pathname + window.location.search,
                    window.location.origin,
                  ),
                )
              }
              variant="ghost"
            >
              {t("common.shareView")}
            </Button>
            <Button
              type="button"
              onClick={() =>
                exportCsv("run-compare.csv", comparisonRows, comparisonColumns)
              }
              variant="ghost"
            >
              {t("common.exportCsv")}
            </Button>
            <Button
              type="button"
              onClick={() =>
                exportJson("run-compare.json", {
                  baseRunId,
                  rows: comparisonRows,
                  targetRunId,
                })
              }
              variant="ghost"
            >
              {t("common.exportJson")}
            </Button>
          </div>
        </div>
      </Card>

      <AsyncSection
        query={{ isLoading, isError, error }}
        loading={
          <Card>
            <p className="text-muted text-sm">{t("pages.runs.loading")}</p>
          </Card>
        }
        errorTitle={t("pages.runs.loadRunDetailsError")}
        empty={comparisonRows.length === 0}
        emptyState={
          <Card>
            <EmptyState
              title={t("pages.runs.unavailableRun")}
              body={t("pages.runs.compare.emptyBody")}
            />
          </Card>
        }
      >
        <Card className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h4 className="text-xl font-semibold">
              {t("pages.runs.compare.deltaTitle")}
            </h4>
            <PrefetchLink
              to={`/runs/${targetRunId}/overview`}
              prefetch="intent"
              className="text-accent text-sm underline"
            >
              {t("pages.runs.compare.openTargetRun")}
            </PrefetchLink>
          </div>
          <DataTable
            rows={comparisonRows}
            rowKey={(row) => row.label}
            columns={comparisonColumns}
          />
        </Card>
      </AsyncSection>
    </div>
  );
}
