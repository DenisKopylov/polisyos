import { useAuthzDecision } from "@/app/authz/AuthzProvider";
import { useConfidenceLedgerRiskSpend } from "@/features/runs/api/useConfidenceLedgerRiskSpend";
import { useDepthNCycleBoardProjection } from "@/features/runs/api/useDepthNCycleBoardProjection";
import { ConfidenceLedgerRiskSpend } from "@/features/runs/components/ConfidenceLedgerRiskSpend";
import { CycleBoard } from "@/features/runs/components/CycleBoard";
import { PanelErrorBoundary } from "@/shared/components/ErrorBoundary";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Card, EmptyState, PanelSkeleton } from "@polisyos/atlas-ui";

function CycleBoardQueryPanel() {
  const { t } = useI18n();
  const query = useDepthNCycleBoardProjection();

  if (query.isLoading) {
    return (
      <Card>
        <PanelSkeleton rows={8} />
      </Card>
    );
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

function ConfidenceLedgerRiskSpendQueryPanel() {
  const { t } = useI18n();
  const query = useConfidenceLedgerRiskSpend();

  if (query.isLoading) {
    return (
      <Card>
        <PanelSkeleton rows={6} />
      </Card>
    );
  }
  if (query.isError || !query.data) {
    return (
      <Card>
        <EmptyState
          body={t("pages.cycleBoard.confidenceLedger.loadErrorBody")}
          title={t("pages.cycleBoard.confidenceLedger.loadErrorTitle")}
        />
      </Card>
    );
  }
  return <ConfidenceLedgerRiskSpend projection={query.data} />;
}

function AuthorizedCycleBoardPage() {
  const { t } = useI18n();
  return (
    <div className="space-y-6">
      <PanelErrorBoundary
        body={t("pages.cycleBoard.boundaryBody")}
        title={t("pages.cycleBoard.boundaryTitle")}
      >
        <CycleBoardQueryPanel />
      </PanelErrorBoundary>
      <PanelErrorBoundary
        body={t("pages.cycleBoard.confidenceLedger.boundaryBody")}
        title={t("pages.cycleBoard.confidenceLedger.boundaryTitle")}
      >
        <ConfidenceLedgerRiskSpendQueryPanel />
      </PanelErrorBoundary>
    </div>
  );
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
