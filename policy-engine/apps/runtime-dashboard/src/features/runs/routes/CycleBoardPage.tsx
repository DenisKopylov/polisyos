import { useAuthzDecision } from "@/app/authz/AuthzProvider";
import { useDepthNCycleBoardProjection } from "@/features/runs/api/useDepthNCycleBoardProjection";
import { CycleBoard } from "@/features/runs/components/CycleBoard";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Card, EmptyState, PanelSkeleton } from "@polisyos/atlas-ui";

function AuthorizedCycleBoardPage() {
  const { t } = useI18n();
  const query = useDepthNCycleBoardProjection();

  if (query.isLoading) {
    return <PanelSkeleton rows={8} />;
  }
  if (query.isError || !query.data) {
    return (
      <Card>
        <EmptyState
          body={t("pages.cycleBoard.loadErrorBody")}
          title={t("pages.cycleBoard.loadErrorTitle")}
        />
      </Card>
    );
  }
  return <CycleBoard projection={query.data} />;
}

export default function CycleBoardPage() {
  const { t } = useI18n();
  const authzDecision = useAuthzDecision();

  if (authzDecision.kind === "unknown") {
    return (
      <Card data-testid="cycle-board-access-unsettled">
        <EmptyState
          body={t("pages.cycleBoard.accessUnsettledBody")}
          title={t("pages.cycleBoard.accessUnsettledTitle")}
        />
      </Card>
    );
  }

  if (!authzDecision.can("runs.review")) {
    return (
      <Card data-testid="cycle-board-access-denied">
        <EmptyState
          body={t("pages.cycleBoard.accessDeniedBody")}
          title={t("pages.cycleBoard.accessDeniedTitle")}
        />
      </Card>
    );
  }

  return <AuthorizedCycleBoardPage />;
}
