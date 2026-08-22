import { useRunAuthorityValues } from "@/api/hooks/useRunAuthorityValues";
import { useI18n } from "@/shared/i18n/LocaleProvider";

export function ScientificDepthPanel({ runId }: { runId: string }) {
  const { t } = useI18n();
  const { values } = useRunAuthorityValues(runId, "scientific");

  return (
    <section data-testid="scientific-depth-panel">
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
