import { lazy } from "react";
import { useParams } from "react-router-dom";

import { useRunInspector } from "@/features/runs/context/RunInspectorContext";
import { coreRunIdFromDetails } from "@/features/runs/routes/useRunDetailSummary";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { PanelSkeleton } from "@polisyos/atlas-ui";

const AgentPipelinePanel = lazy(
  () => import("@/features/runs/components/AgentPipelinePanel"),
);

function AgentsTabContent() {
  const { t } = useI18n();
  const summary = useRunInspector();
  const coreRunId = summary.coreRunId ?? coreRunIdFromDetails(summary.run);

  if (summary.runDetailsQuery.isError) {
    throw summary.runDetailsQuery.error;
  }
  if (summary.agentsQuery.isError) {
    throw summary.agentsQuery.error;
  }
  if (summary.runBootstrapPending || summary.agentsQuery.isLoading) {
    return <PanelSkeleton rows={6} />;
  }
  if (!coreRunId || !summary.pipeline) {
    return (
      <p role="status" data-testid="run-agents-unavailable">
        {t("common.unavailable")}
      </p>
    );
  }

  return <AgentPipelinePanel payload={summary.pipeline} />;
}

export default function AgentsTab() {
  const { t } = useI18n();
  const { runId } = useParams();

  if (!runId) {
    return null;
  }

  return (
    <div data-testid="run-tab-agents">
      <FeatureAsyncBoundary
        feature="runs.agents.pipeline"
        title={t("pages.runs.agentsLoadError")}
        body={t("common.pageErrorBody")}
        loading={<PanelSkeleton rows={6} />}
        resetKeys={[runId]}
      >
        <AgentsTabContent />
      </FeatureAsyncBoundary>
    </div>
  );
}
