import { Suspense, lazy, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { useNodeDebug } from "@/api/hooks/useNodeDebug";
import { useRunErrors, useSuspenseRunErrors } from "@/api/hooks/useRunErrors";
import { useRunNodes } from "@/api/hooks/useRunNodes";
import {
  useRunTimeline,
  useSuspenseRunTimeline,
} from "@/api/hooks/useRunTimeline";
import { AuditTimeline } from "@/features/runs/components/AuditTimeline";
import { buildAuditTrail } from "@/features/runs/domain/compare";
import { MetricCard } from "@/features/runs/components/MetricCard";
import { useRunInspector } from "@/features/runs/context/RunInspectorContext";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatDate, formatNumber } from "@/shared/lib/utils";
import { FeatureErrorBoundary } from "@/shared/components/ErrorBoundary";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import {
  PanelSkeleton,
  VirtualTable,
  VIRTUALIZATION_THRESHOLD,
} from "@polisyos/atlas-ui";
import { DataTable } from "@/shared/ui";

const ErrorsPanel = lazy(
  () => import("@/features/runs/components/debug/ErrorsPanel"),
);
const NodeDebugPanel = lazy(
  () => import("@/features/runs/components/debug/NodeDebugPanel"),
);

function DebugTimelineContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const timelineQuery = useSuspenseRunTimeline(runId);
  const timelineEvents = timelineQuery.data.timeline.events ?? [];

  return (
    <>
      {timelineEvents.length < VIRTUALIZATION_THRESHOLD ? (
        <DataTable
          rows={timelineEvents}
          rowKey={(event) => `${event.index}-${event.event}`}
          columns={[
            {
              key: "event",
              header: t("pages.runs.timelineEvents"),
              render: (event) => (
                <div>
                  <p className="font-semibold">{event.event}</p>
                  <p className="text-muted text-xs">{event.phase}</p>
                </div>
              ),
            },
            {
              key: "started",
              header: t("pages.runs.started"),
              render: (event) => formatDate(event.timestamp),
            },
            {
              key: "duration",
              header: t("pages.runs.duration"),
              render: (event) =>
                t("pages.runs.timelineIndex", { index: event.index }),
            },
            {
              key: "artifacts",
              header: t("pages.runs.rootArtifacts"),
              render: (event) =>
                formatNumber(
                  (event.input_artifact_ids?.length ?? 0) +
                    (event.output_artifact_ids?.length ?? 0),
                ),
            },
          ]}
        />
      ) : (
        <VirtualTable
          ariaLabel={t("pages.runs.timelineEvents")}
          columns={[
            {
              key: "event",
              header: t("pages.runs.timelineEvents"),
              render: (event) => (
                <div>
                  <p className="font-semibold">{event.event}</p>
                  <p className="text-muted text-xs">{event.phase}</p>
                </div>
              ),
            },
            {
              key: "started",
              header: t("pages.runs.started"),
              render: (event) => formatDate(event.timestamp),
            },
            {
              key: "duration",
              header: t("pages.runs.duration"),
              render: (event) =>
                t("pages.runs.timelineIndex", { index: event.index }),
            },
            {
              key: "artifacts",
              header: t("pages.runs.rootArtifacts"),
              render: (event) =>
                formatNumber(
                  (event.input_artifact_ids?.length ?? 0) +
                    (event.output_artifact_ids?.length ?? 0),
                ),
            },
          ]}
          estimateRowHeight={58}
          rowKey={(event) => `${event.index}-${event.event}`}
          rows={timelineEvents}
        />
      )}
    </>
  );
}

function DebugErrorsContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const summary = useRunInspector();
  const timelineQuery = useSuspenseRunTimeline(runId);
  const errorsQuery = useSuspenseRunErrors(runId);
  const timelineEvents = timelineQuery.data.timeline.events ?? [];
  const runErrors = errorsQuery.data.errors ?? [];
  const auditTrail = buildAuditTrail({
    errors: runErrors,
    governanceIssues: summary.governanceIssues,
    timelineEvents,
  });

  return (
    <div className="space-y-5">
      <AuditTimeline
        entries={auditTrail}
        emptyTitle={t("pages.runs.overviewTimelineEmptyTitle")}
        emptyBody={t("pages.runs.overviewTimelineEmptyBody")}
      />
      <ErrorsPanel errors={runErrors} />
    </div>
  );
}

export default function DebugTab() {
  const { t } = useI18n();
  const { runId } = useParams();
  const summary = useRunInspector();
  const nodesQuery = useRunNodes(runId, Boolean(summary.run));
  const timelineQuery = useRunTimeline(runId, Boolean(summary.run));
  const errorsQuery = useRunErrors(runId, Boolean(summary.run));
  const nodeRecords = nodesQuery.data?.nodes ?? [];
  const timelineEvents = timelineQuery.data?.timeline.events ?? [];
  const runErrors = errorsQuery.data?.errors ?? [];
  const [selectedAlias, setSelectedAlias] = useState<string | null>(null);

  useEffect(() => {
    if (nodeRecords.length === 0) {
      setSelectedAlias(null);
      return;
    }
    setSelectedAlias((current) =>
      current && nodeRecords.some((node) => node.alias === current)
        ? current
        : (nodeRecords[0]?.alias ?? null),
    );
  }, [nodeRecords]);

  const nodeDebugQuery = useNodeDebug(
    runId,
    selectedAlias,
    Boolean(summary.run) && Boolean(selectedAlias),
  );

  if (!runId) {
    return null;
  }

  return (
    <div className="space-y-5" data-testid="run-tab-debug">
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard
          label={t("pages.runs.timelineEvents")}
          value={formatNumber(timelineEvents.length)}
        />
        <MetricCard
          label={t("pages.runs.nodesColumns.alias")}
          value={formatNumber(nodeRecords.length)}
        />
        <MetricCard
          label={t("pages.runs.debugRunErrors")}
          value={formatNumber(runErrors.length)}
        />
        <MetricCard
          label={t("pages.runs.selectedNode")}
          value={selectedAlias ?? "-"}
        />
      </div>

      <FeatureAsyncBoundary
        feature="runs.debug.timeline"
        title={t("pages.runs.timelineLoadError")}
        body={t("common.pageErrorBody")}
        loading={<PanelSkeleton rows={4} />}
        resetKeys={[runId]}
      >
        <DebugTimelineContent runId={runId} />
      </FeatureAsyncBoundary>

      <FeatureErrorBoundary
        feature="runs.debug.nodePanel"
        title={t("pages.runs.debugLoadError")}
        body={t("common.pageErrorBody")}
        resetKeys={[runId, selectedAlias]}
      >
        <Suspense fallback={<PanelSkeleton rows={4} />}>
          <div className="space-y-3">
            {nodesQuery.isLoading ? <PanelSkeleton rows={4} /> : null}
            {nodeRecords.length > 0 ? (
              <NodeDebugPanel
                nodes={nodeRecords}
                selectedAlias={selectedAlias}
                onSelectAlias={setSelectedAlias}
                debugData={nodeDebugQuery.data?.debug ?? null}
              />
            ) : null}
            {nodeDebugQuery.isLoading ? <PanelSkeleton rows={3} /> : null}
          </div>
        </Suspense>
      </FeatureErrorBoundary>

      <FeatureAsyncBoundary
        feature="runs.debug.audit"
        title={t("pages.runs.runErrorsLoadError")}
        body={t("common.pageErrorBody")}
        loading={<PanelSkeleton rows={5} />}
        resetKeys={[runId]}
      >
        <DebugErrorsContent runId={runId} />
      </FeatureAsyncBoundary>
    </div>
  );
}
