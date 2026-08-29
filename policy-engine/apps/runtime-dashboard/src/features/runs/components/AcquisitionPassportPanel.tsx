import type { AcquisitionGrowthPayload } from "@polisyos/runtime-api-client";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Card } from "@polisyos/atlas-ui";

export function AcquisitionPassportPanel({
  history,
}: {
  history: AcquisitionGrowthPayload["n13b_history"];
}) {
  const { t } = useI18n();
  const qualification = history.epoch_qualification;
  return (
    <Card
      className="space-y-3 p-4"
      data-acquisition-raw={JSON.stringify({
        admission: history.admission,
        epoch_qualification: qualification,
        overlay_epoch_count: history.overlay_epoch_count,
      })}
      data-testid="acquisition-passport-panel"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">
          {t("pages.cycleBoard.acquisition.passport.title")}
        </h2>
        <Badge kind="warn">{qualification.status}</Badge>
      </header>
      <dl className="grid gap-2 text-sm md:grid-cols-2">
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.passport.epochState")}
          </dt>
          <dd>{qualification.epoch_state}</dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.passport.code")}
          </dt>
          <dd>{qualification.code}</dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.passport.authority")}
          </dt>
          <dd>
            {qualification.appointment_state} · {qualification.authority_role}
          </dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.passport.overlayEpochs")}
          </dt>
          <dd>{history.overlay_epoch_count}</dd>
        </div>
      </dl>
      <p className="text-sm">
        <strong>
          {t("pages.cycleBoard.acquisition.passport.appointmentWouldEstablish")}
          :
        </strong>{" "}
        {qualification.appointment_would_establish}
      </p>
      <div>
        <h3 className="text-sm font-semibold">
          {t(
            "pages.cycleBoard.acquisition.passport.appointmentWouldNotEstablish",
          )}
        </h3>
        <ul className="list-disc pl-5 text-sm">
          {qualification.appointment_would_not_establish.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
