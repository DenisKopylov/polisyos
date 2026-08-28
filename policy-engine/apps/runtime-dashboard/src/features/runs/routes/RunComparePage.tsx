import { useParams, useSearchParams } from "react-router-dom";

import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { PolicyDiffView } from "@/features/runs/compare/PolicyDiffView";
import { CompareCommandDialog } from "@/features/runs/compare/CompareCommandDialog";
import { useEpochStaleness } from "@/features/runs/api/useEpochStaleness";
import { epochSemanticsFromProjection } from "@/features/runs/components/EpochStalenessView";
import { parseRunCompareSearchParams } from "@/features/runs/domain/searchParams";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Card, EmptyState } from "@polisyos/atlas-ui";
import {
  epochNonreceipt,
  TimeSemanticsLabel,
} from "@/shared/ui/temporal/TimeSemanticsLabel";

function CompareEpochChrome({ runId }: { runId: string }) {
  const { t } = useI18n();
  const query = useEpochStaleness({ runId });
  const projection = query.data?.projection;
  return (
    <section
      aria-label={t("epochChrome.compareRun", { runId })}
      className="rounded-lg border border-[var(--line)] p-3"
      data-testid={`compare-epoch-${runId}`}
    >
      <p className="mb-2 font-mono text-xs font-semibold break-all">{runId}</p>
      <TimeSemanticsLabel
        epochSemantics={
          projection
            ? epochSemanticsFromProjection(projection)
            : epochNonreceipt()
        }
        payloadAsOf={projection?.owner_as_of}
        txAt={projection?.temporal_scope.tx_at}
        validAt={projection?.temporal_scope.valid_at}
      />
    </section>
  );
}

export default function RunComparePage() {
  const { t } = useI18n();
  const params = useParams();
  const [searchParams] = useSearchParams();
  const { base, target } = parseRunCompareSearchParams(searchParams);
  const runAId = params.runA ?? base;
  const runBId = params.runB ?? target;

  useTelemetryReadyMark("runs.compare.page", { routeId: "runs.compare" });

  if (!runAId || !runBId) {
    return (
      <Card className="space-y-4">
        <EmptyState
          title={t("pages.runs.compare.requiredTitle")}
          body={t("pages.runs.compare.requiredBody")}
        />
        <CompareCommandDialog />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div
        aria-label={t("epochChrome.compareBoundary")}
        className="grid gap-4 md:grid-cols-2"
        data-testid="compare-epoch-boundary"
      >
        <CompareEpochChrome runId={runAId} />
        <CompareEpochChrome runId={runBId} />
      </div>
      <PolicyDiffView runAId={runAId} runBId={runBId} />
    </div>
  );
}
