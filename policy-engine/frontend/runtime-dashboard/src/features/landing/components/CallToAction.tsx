import { Button } from "@/shared/ui";
import { useI18n } from "@/i18n/LocaleProvider";

export function CallToAction() {
  const { t } = useI18n();

  return (
    <section className="flex flex-col items-center gap-4 px-6 py-20 text-center">
      <h2 className="text-2xl font-bold tracking-tight text-[var(--ink)]">
        {t("landing.ctaTitle")}
      </h2>
      <p className="text-base text-[var(--slate)]">
        {t("landing.ctaSubtitle")}
      </p>
      <div className="pt-4">
        <Button variant="primary" size="lg" to="/login">
          {t("landing.heroCta")}
        </Button>
      </div>
    </section>
  );
}
