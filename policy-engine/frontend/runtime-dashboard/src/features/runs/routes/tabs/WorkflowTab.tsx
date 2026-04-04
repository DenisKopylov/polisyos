import { lazy } from "react";
import { useParams } from "react-router-dom";

import { useSuspenseRunLineage } from "@/api/hooks/useRunLineage";
import { useSuspenseRunWorkflow } from "@/api/hooks/useRunWorkflow";
import { MetricCard } from "@/features/runs/components/MetricCard";
import { useI18n } from "@/i18n/LocaleProvider";
import { formatBytes, formatNumber } from "@/lib/utils";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import { Card, EmptyState, PanelSkeleton } from "@/shared/ui";

const LineageGraph = lazy(() => import("@/shared/ui/LineageGraph"));
const WorkflowDagPanel = lazy(
  () => import("@/features/runs/components/WorkflowDagPanel"),
);

function WorkflowPanelContent({ runId }: { runId: string }) {
  const workflowQuery = useSuspenseRunWorkflow(runId);

  return (
    <WorkflowDagPanel payload={workflowQuery.data.workflow} runId={runId} />
  );
}

function LineagePanelContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const lineageQuery = useSuspenseRunLineage(runId);
  const lineage = lineageQuery.data.lineage;

  if (lineage.nodes.length === 0 && lineage.edges.length === 0) {
    return (
      <EmptyState
        title={t("pages.runs.lineageEmptyTitle")}
        body={t("pages.runs.lineageEmptyBody")}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard
          label={t("pages.runs.lineageNodes")}
          value={formatNumber(lineage.total_nodes)}
        />
        <MetricCard
          label={t("pages.runs.lineageEdges")}
          value={formatNumber(lineage.total_edges)}
        />
        <MetricCard
          label={t("pages.runs.lineageComplete")}
          value={lineage.is_complete ? t("common.yes") : t("common.no")}
        />
        <MetricCard
          label={t("pages.runs.lineageSize")}
          value={formatBytes(lineage.total_size_bytes)}
        />
      </div>
      <LineageGraph
        nodes={lineage.nodes}
        edges={lineage.edges}
        rootArtifactIds={lineage.root_artifact_ids}
      />
      {lineage.missing_artifact_ids.length > 0 ? (
        <p className="text-warning text-sm">
          {t("pages.runs.missingArtifacts", {
            artifacts: lineage.missing_artifact_ids.join(", "),
          })}
        </p>
      ) : null}
    </div>
  );
}

export default function WorkflowTab() {
  const { t } = useI18n();
  const { runId } = useParams();

  if (!runId) {
    return null;
  }

  return (
    <div className="space-y-5" data-testid="run-tab-workflow">
      <Card className="space-y-4">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{t("pages.runs.sections.workflow")}</p>
            <h4>{t("pages.runs.tabs.workflow")}</h4>
          </div>
        </div>
        <FeatureAsyncBoundary
          feature="runs.workflow.graph"
          title={t("pages.runs.workflowLoadError")}
          body={t("common.pageErrorBody")}
          loading={
            <PanelSkeleton rows={5} className="border-0 bg-transparent p-0" />
          }
          resetKeys={[runId]}
        >
          <WorkflowPanelContent runId={runId} />
        </FeatureAsyncBoundary>
      </Card>

      <Card className="space-y-4">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{t("pages.runs.sections.lineage")}</p>
            <h4>{t("pages.runs.tabs.workflowLineage")}</h4>
          </div>
        </div>
        <FeatureAsyncBoundary
          feature="runs.workflow.lineage"
          title={t("pages.runs.lineageLoadError")}
          body={t("common.pageErrorBody")}
          loading={
            <PanelSkeleton rows={5} className="border-0 bg-transparent p-0" />
          }
          resetKeys={[runId]}
        >
          <LineagePanelContent runId={runId} />
        </FeatureAsyncBoundary>
      </Card>
    </div>
  );
}
