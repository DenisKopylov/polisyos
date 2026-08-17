import { useRunAuthorityValues } from "@/api/hooks/useRunAuthorityValues";
import { useI18n } from "@/shared/i18n/LocaleProvider";

export function PublicSectorReadinessPanel({ runId }: { runId: string }) {
  const { t } = useI18n();
  const { values } = useRunAuthorityValues(runId, "readiness");

  return (
    <section data-testid="public-sector-readiness-panel">
      {t("common.unavailable")}
      <ul data-testid="authority-refusal-list">
        {values.map((value) => (
          <li
            data-owner-surface={value.ownerSurface}
            data-refusal-code={value.refusalCode}
            data-state={value.state}
            data-testid="authority-refusal"
            data-value-id={value.valueId}
            key={value.valueId}
          >
            {value.detail}
          </li>
        ))}
      </ul>
    </section>
  );
}
