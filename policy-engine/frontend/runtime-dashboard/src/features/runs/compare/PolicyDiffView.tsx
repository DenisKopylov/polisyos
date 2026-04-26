import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { fromApiTemporalScope } from "@/app/providers/temporal-scope";
import { PrefetchLink } from "@/app/routes/PrefetchLink";
import { useI18n } from "@/i18n/LocaleProvider";
import {
  AsyncSection,
  Button,
  EmptyState,
  copyShareLink,
  exportJson,
} from "@/shared/ui";
import { Quantity } from "@/shared/ui/quantity";

import { CausalDeltaStrip } from "./CausalDeltaStrip";
import { CompareCommandDialog } from "./CompareCommandDialog";
import { ComparisonFramePanel } from "./ComparisonFramePanel";
import { PolicyDiffLayout } from "./PolicyDiffLayout";
import type { DeltaQuantity } from "./compare-types";
import { useDiffData } from "./useDiffData";
import { AssumptionDiff } from "./delta-widgets/AssumptionDiff";
import { BudgetFlowDiff } from "./delta-widgets/BudgetFlowDiff";
import { DistributionDelta } from "./delta-widgets/DistributionDelta";
import { GovernanceRadarDiff } from "./delta-widgets/GovernanceRadarDiff";
import { IdentifiabilityTrajectory } from "./delta-widgets/IdentifiabilityTrajectory";
import { OutcomeDelta } from "./delta-widgets/OutcomeDelta";
import { ProvenanceDrift } from "./delta-widgets/ProvenanceDrift";
import { SubgroupDeltaMatrix } from "./delta-widgets/SubgroupDeltaMatrix";

type PolicyDiffViewProps = {
  runAId?: string;
  runBId?: string;
};

export function PolicyDiffView({ runAId, runBId }: PolicyDiffViewProps) {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const compareQuery = useDiffData(runAId, runBId);
  const [activeMetricId, setActiveMetricId] = useState<string | null>(null);
  const payload = compareQuery.data;
  const deltas = payload?.deltas ?? [];
  const [firstDelta] = deltas;
  const metricFromUrl = searchParams.get("metric");
  const selectedMetricId = activeMetricId ?? metricFromUrl;
  const hasNoDeltas = Boolean(payload && !deltas.length);
  const activeDelta = useMemo(
    () =>
      selectedMetricId
        ? deltas.find((delta) => delta.metric_id === selectedMetricId)
        : firstDelta,
    [selectedMetricId, deltas, firstDelta],
  );
  const temporalScope = fromApiTemporalScope(payload?.temporal_scope);
  useEffect(() => {
    setActiveMetricId(metricFromUrl);
  }, [metricFromUrl]);
  const selectMetric = useCallback(
    (metricId: string) => {
      setActiveMetricId(metricId);
      const next = new URLSearchParams(searchParams);
      next.set("metric", metricId);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  if (!runAId || !runBId) {
    return (
      <section className="panel rounded-[var(--radius-panel)] p-6">
        <EmptyState
          title={t("pages.runs.policyDiff.chooseTitle")}
          body={t("pages.runs.policyDiff.chooseBody")}
        />
        <div className="mt-4">
          <CompareCommandDialog />
        </div>
      </section>
    );
  }

  return (
    <div
      className="space-y-5"
      data-active-metric-id={activeDelta?.metric_id}
      data-testid="policy-diff-view"
    >
      <section className="panel rounded-[var(--radius-panel)] p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{t("pages.runs.policyDiff.title")}</p>
            <h1 className="text-2xl font-semibold">
              {runAId} {t("pages.runs.policyDiff.to")} {runBId}
            </h1>
            <p className="topbar-subtitle">
              {t("pages.runs.policyDiff.subtitle")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <CompareCommandDialog currentRunId={runAId} targetRunId={runBId} />
            <Button
              type="button"
              variant="ghost"
              onClick={() =>
                void copyShareLink(
                  new URL(
                    window.location.pathname + window.location.search,
                    window.location.origin,
                  ),
                )
              }
            >
              {t("pages.runs.policyDiff.share")}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() =>
                exportJson("policy-diff.json", {
                  runAId,
                  runBId,
                  temporalScope,
                  payload,
                })
              }
            >
              {t("pages.runs.policyDiff.exportJson")}
            </Button>
          </div>
        </div>
      </section>

      <AsyncSection
        query={compareQuery}
        loading={
          <section className="panel rounded-[var(--radius-panel)] p-4">
            <p className="text-muted text-sm">
              {t("pages.runs.policyDiff.loading")}
            </p>
          </section>
        }
        errorTitle={t("pages.runs.policyDiff.loadError")}
        empty={hasNoDeltas}
        emptyState={
          <section className="panel rounded-[var(--radius-panel)] p-6">
            <EmptyState
              title={t("pages.runs.policyDiff.noSafeDeltasTitle")}
              body={t("pages.runs.policyDiff.noSafeDeltasBody")}
            />
            {payload ? (
              <div className="mt-4">
                <ComparisonFramePanel
                  frame={payload.comparison_frame}
                  comparability={payload.comparability}
                />
              </div>
            ) : null}
          </section>
        }
      >
        {payload ? (
          <>
            <ComparisonFramePanel
              frame={payload.comparison_frame}
              comparability={payload.comparability}
            />

            <PolicyDiffLayout
              leftPane={
                <RunComparePane
                  title={t("pages.runs.policyDiff.runA")}
                  runId={runAId}
                  deltas={deltas}
                  side="a"
                  activeDelta={activeDelta}
                />
              }
              deltaRail={
                <CausalDeltaStrip
                  deltas={deltas}
                  activeMetricId={activeDelta?.metric_id}
                  onSelectMetric={selectMetric}
                />
              }
              rightPane={
                <RunComparePane
                  title={t("pages.runs.policyDiff.runB")}
                  runId={runBId}
                  deltas={deltas}
                  side="b"
                  activeDelta={activeDelta}
                />
              }
            />

            <div className="grid gap-4 xl:grid-cols-2">
              <OutcomeDelta
                deltas={deltas}
                activeMetricId={activeDelta?.metric_id}
              />
              <DistributionDelta deltas={deltas} />
              <SubgroupDeltaMatrix deltas={deltas} />
              <IdentifiabilityTrajectory deltas={deltas} />
              <GovernanceRadarDiff deltas={deltas} />
              <BudgetFlowDiff deltas={deltas} />
              <ProvenanceDrift deltas={deltas} />
              <AssumptionDiff
                frame={payload.comparison_frame}
                deltas={deltas}
              />
            </div>
          </>
        ) : null}
      </AsyncSection>
    </div>
  );
}

function RunComparePane({
  activeDelta,
  deltas,
  runId,
  side,
  title,
}: {
  activeDelta?: DeltaQuantity;
  deltas: DeltaQuantity[];
  runId: string;
  side: "a" | "b";
  title: string;
}) {
  const { t } = useI18n();
  const activeValue = activeDelta?.[side];
  return (
    <section className="panel min-h-full space-y-4 rounded-[var(--radius-panel)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">{title}</p>
          <h2 className="text-xl font-semibold">{runId}</h2>
        </div>
        <PrefetchLink
          to={`/runs/${runId}/overview`}
          prefetch="intent"
          className="text-accent text-sm underline"
        >
          {t("pages.runs.policyDiff.openRun")}
        </PrefetchLink>
      </div>
      {activeDelta && activeValue ? (
        <div
          className="border-line rounded-lg border p-3"
          data-testid={`policy-diff-active-${side}`}
        >
          <p className="text-muted text-xs font-semibold uppercase">
            {t("pages.runs.policyDiff.selectedMetric")}
          </p>
          <p className="mt-1 font-semibold">{activeDelta.label}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Quantity
              value={activeValue}
              variant="dense"
              provenanceMode="auto"
            />
            {activeDelta.delta_absolute ? (
              <Quantity
                value={activeDelta.delta_absolute}
                variant="dense"
                provenanceMode="auto"
              />
            ) : null}
          </div>
        </div>
      ) : null}
      <div className="space-y-2">
        {deltas.map((delta) => (
          <div
            key={`${side}-${delta.metric_id}`}
            className="border-line flex items-center justify-between gap-3 rounded-lg border p-3"
          >
            <span className="text-sm font-medium">{delta.label}</span>
            <span className="text-muted text-xs">
              {delta[side]?.point ?? t("pages.runs.policyDiff.notAvailable")}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
