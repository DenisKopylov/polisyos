import { useAuthzDecision } from "@/app/authz/AuthzProvider";
import { useConfidenceLedgerRiskSpend } from "@/features/runs/api/useConfidenceLedgerRiskSpend";
import { useDepthNCycleBoardProjection } from "@/features/runs/api/useDepthNCycleBoardProjection";
import { ConfidenceLedgerRiskSpend } from "@/features/runs/components/ConfidenceLedgerRiskSpend";
import { CycleBoard } from "@/features/runs/components/CycleBoard";
import { PanelErrorBoundary } from "@/shared/components/ErrorBoundary";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  epochNonreceipt,
  TimeSemanticsLabel,
} from "@/shared/ui/temporal/TimeSemanticsLabel";
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
  const packet =
    !query.isLoading &&
    !query.isError &&
    query.data?.status === "exact"
      ? query.data.packet
      : null;
  const surface = query.isLoading ? (
      <Card>
        <PanelSkeleton rows={6} />
      </Card>
    ) : query.isError || !query.data ? (
      <Card>
        <EmptyState
          body={t("pages.cycleBoard.confidenceLedger.loadErrorBody")}
          title={t("pages.cycleBoard.confidenceLedger.loadErrorTitle")}
        />
      </Card>
    ) : (
      <ConfidenceLedgerRiskSpend projection={query.data} />
    );
  return (
    <>
      <div data-testid="confidence-ledger-risk-spend-query-time-semantics">
        <TimeSemanticsLabel
          epochSemantics={epochNonreceipt()}
          freshness={packet?.freshness}
          payloadAsOf={packet?.as_of}
        />
      </div>
      {surface}
    </>
  );
}

function AuthorizedCycleBoardPage() {
  const { t } = useI18n();
  return (
    <div className="space-y-6" data-ds17-confidence-ledger-page>
      <style>
        {
          "[data-ds17-confidence-ledger-page] :is(button, input, select, textarea) { appearance: none !important; } [data-ds17-confidence-ledger-page] :is(ol, ul, menu, summary) { list-style: none !important; }"
        }
      </style>
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
