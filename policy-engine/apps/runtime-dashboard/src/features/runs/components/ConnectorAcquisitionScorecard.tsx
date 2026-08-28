import type { AcquisitionGrowthPayload } from "@polisyos/runtime-api-client";

import { presentConnectorAcquisitionScorecard } from "@/features/runs/domain/acquisitionRoutePresentation";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Card } from "@polisyos/atlas-ui";

export function ConnectorAcquisitionScorecard({
  carrierLiveness,
  familyCount,
}: {
  carrierLiveness: AcquisitionGrowthPayload["carrier_liveness"];
  familyCount: number;
}) {
  const { t } = useI18n();
  const visible = presentConnectorAcquisitionScorecard(carrierLiveness);
  return (
    <Card
      className="space-y-3 p-4"
      data-acquisition-raw={JSON.stringify(visible.raw)}
      data-connector-health={visible.health}
      data-testid="connector-acquisition-scorecard"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">
          {t("pages.cycleBoard.acquisition.connector.title")}
        </h2>
        <Badge kind={visible.health === "degraded" ? "warn" : "outline"}>
          {visible.health}
        </Badge>
      </header>
      <p className="text-muted-foreground text-sm">
        {t("pages.cycleBoard.acquisition.connector.familyCount", {
          count: familyCount,
        })}
      </p>
      <dl className="grid gap-2 text-sm md:grid-cols-3">
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.connector.connector")}
          </dt>
          <dd>{visible.connectorId}</dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.connector.tier")}
          </dt>
          <dd>{visible.executionTier}</dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.connector.disposition")}
          </dt>
          <dd>{visible.carrierDisposition}</dd>
        </div>
      </dl>
      {visible.tierDecayFindings.length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {visible.tierDecayFindings.map((finding) => (
            <li className="font-mono" key={finding}>
              {finding}
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
