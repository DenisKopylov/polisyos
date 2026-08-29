import type { AcquisitionGrowthPayload } from "@polisyos/runtime-api-client";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Card } from "@polisyos/atlas-ui";

export function AcquisitionQuarantineLedger({
  history,
}: {
  history: AcquisitionGrowthPayload["n13b_history"];
}) {
  const { t } = useI18n();
  return (
    <Card
      className="space-y-3 p-4"
      data-acquisition-raw={JSON.stringify(history)}
      data-testid="acquisition-quarantine-ledger"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">
          {t("pages.cycleBoard.acquisition.quarantine.title")}
        </h2>
        <Badge
          kind={history.quarantine === "raw_terminal" ? "warn" : "outline"}
        >
          {history.quarantine}
        </Badge>
      </header>
      <p className="text-sm font-semibold">
        {t("pages.cycleBoard.acquisition.quarantine.counts", {
          admitted: history.response_admitted_count,
          raw: history.raw_response_count,
        })}
      </p>
      <dl className="grid gap-2 text-sm md:grid-cols-3">
        <div>
          <dt>{t("pages.cycleBoard.acquisition.quarantine.worldGrowth")}</dt>
          <dd>{history.world_growth}</dd>
        </div>
        <div>
          <dt>{t("pages.cycleBoard.acquisition.quarantine.reentry")}</dt>
          <dd>{history.reentry}</dd>
        </div>
        <div>
          <dt>{t("pages.cycleBoard.acquisition.quarantine.terminal")}</dt>
          <dd>{history.terminal_count}</dd>
        </div>
      </dl>
    </Card>
  );
}
