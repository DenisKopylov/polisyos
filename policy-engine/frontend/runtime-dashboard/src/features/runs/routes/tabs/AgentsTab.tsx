import { lazy } from "react";
import { useParams } from "react-router-dom";

import { useSuspenseRunAgents } from "@/api/hooks/useRunAgents";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import { useI18n } from "@/i18n/LocaleProvider";
import { PanelSkeleton } from "@/shared/ui";

const AgentPipelinePanel = lazy(
  () => import("@/features/runs/components/AgentPipelinePanel"),
);

function AgentsTabContent({ runId }: { runId: string }) {
  const agentsQuery = useSuspenseRunAgents(runId);

  return <AgentPipelinePanel payload={agentsQuery.data.pipeline} />;
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
        <AgentsTabContent runId={runId} />
      </FeatureAsyncBoundary>
    </div>
  );
}
