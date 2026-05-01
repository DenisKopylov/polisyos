import { lazy, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";

import { useSuspenseGovernanceDebug } from "@/api/hooks/useGovernanceDebug";
import { useReviewCollaborationEnabled } from "@/app/authz/AuthzProvider";
import {
  ReviewCursorLayer,
  ReviewLockNotice,
  ReviewPresenceSummary,
} from "@/app/realtime/ReviewCollaborationIndicators";
import { buildGovernanceReviewId } from "@/app/realtime/reviewIds";
import { useReviewCollaborationSurface } from "@/app/realtime/useReviewCollaborationSurface";
import { DisputeRegistryPanel } from "@/features/runs/components/DisputeRegistryPanel";
import { PublicSectorReadinessPanel } from "@/features/runs/components/PublicSectorReadinessPanel";
import { useRunInspector } from "@/features/runs/context/RunInspectorContext";
import { normalizeGovernanceIssues } from "@/lib/domain/governance";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import { useI18n } from "@/i18n/LocaleProvider";
import {
  markUiMilestone,
  measureUiLatency,
} from "@/shared/telemetry/performance";
import { PanelSkeleton } from "@/shared/ui";

const GovernanceReport = lazy(
  () => import("@/features/runs/components/GovernanceReport"),
);

function GovernanceTabContent({ runId }: { runId: string }) {
  const summary = useRunInspector();
  const governanceQuery = useSuspenseGovernanceDebug(runId);
  const governanceIssues = normalizeGovernanceIssues(
    governanceQuery.data.debug.issues,
  );
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const collaborationEnabled = useReviewCollaborationEnabled();
  const collaboration = useReviewCollaborationSurface({
    enabled: collaborationEnabled,
    reviewId: buildGovernanceReviewId(runId),
    runId,
    surfaceRef,
  });

  useEffect(() => {
    markUiMilestone("runs.governance.primary.ready", {
      routeId: "runs.detail.governance",
      surface: "governance",
    });
    measureUiLatency({
      context: {
        routeId: "runs.detail.governance",
        surface: "governance",
      },
      endMark: "runs.governance.primary.ready",
      metric: "time_to_decision_ms",
    });
  }, []);

  return (
    <div ref={surfaceRef} className="relative space-y-3">
      {collaborationEnabled ? (
        <div className="space-y-2">
          <ReviewPresenceSummary
            participants={collaboration.participants}
            status={collaboration.status}
          />
          <ReviewLockNotice lock={collaboration.lock} />
        </div>
      ) : null}
      <ReviewCursorLayer cursors={collaboration.cursors} />
      <GovernanceReport data={governanceQuery.data.debug} />
      <DisputeRegistryPanel issues={governanceIssues} runId={runId} />
      <PublicSectorReadinessPanel runId={runId} summary={summary} />
    </div>
  );
}

export default function GovernanceTab() {
  const { t } = useI18n();
  const { runId } = useParams();

  if (!runId) {
    return null;
  }

  return (
    <div data-testid="run-tab-governance">
      <FeatureAsyncBoundary
        feature="runs.governance.report"
        title={t("pages.runs.governanceLoadError")}
        body={t("common.pageErrorBody")}
        loading={<PanelSkeleton rows={6} />}
        resetKeys={[runId]}
      >
        <GovernanceTabContent runId={runId} />
      </FeatureAsyncBoundary>
    </div>
  );
}
