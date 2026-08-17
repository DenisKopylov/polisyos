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
            data-owner-surface={value.owner_surface}
            data-refusal-code={value.refusal_code}
            data-state={value.state}
            data-value-id={value.value_id}
            key={value.value_id}
          >
            {value.reason}
          </li>
        ))}
      </ul>
    </section>
  );
}
