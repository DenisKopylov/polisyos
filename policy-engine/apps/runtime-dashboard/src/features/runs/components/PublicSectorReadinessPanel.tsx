import { useI18n } from "@/shared/i18n/LocaleProvider";

export function PublicSectorReadinessPanel() {
  const { t } = useI18n();

  return (
    <section data-testid="public-sector-readiness-panel">
      {t("common.unavailable")}
    </section>
  );
}
