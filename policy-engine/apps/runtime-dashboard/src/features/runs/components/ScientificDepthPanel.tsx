import { useI18n } from "@/shared/i18n/LocaleProvider";

export function ScientificDepthPanel() {
  const { t } = useI18n();

  return (
    <section data-testid="scientific-depth-panel">
      {t("common.unavailable")}
    </section>
  );
}
