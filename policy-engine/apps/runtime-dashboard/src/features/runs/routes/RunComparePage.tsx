import { useParams, useSearchParams } from "react-router-dom";

import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { PolicyDiffView } from "@/features/runs/compare/PolicyDiffView";
import { CompareCommandDialog } from "@/features/runs/compare/CompareCommandDialog";
import { parseRunCompareSearchParams } from "@/features/runs/domain/searchParams";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Card, EmptyState } from "@polisyos/atlas-ui";

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

  return <PolicyDiffView runAId={runAId} runBId={runBId} />;
}
