import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";

export function SignatureBlock() {
  const { t } = useOptionalI18n();
  return (
    <section className="mt-6 grid gap-4 border-t border-black/30 pt-4 text-sm md:grid-cols-2">
      <div>
        <p className="font-semibold">
          {t("pages.artifacts.bureaucratic.signatureTitle")}
        </p>
        <div className="mt-8 border-b border-black/50" aria-hidden="true" />
        <p className="text-muted mt-1 text-xs">
          {t("pages.artifacts.bureaucratic.signatureHint")}
        </p>
      </div>
      <div>
        <p className="font-semibold">
          {t("pages.artifacts.bureaucratic.sealTitle")}
        </p>
        <div className="mt-8 border-b border-black/50" aria-hidden="true" />
        <p className="text-muted mt-1 text-xs">
          {t("pages.artifacts.bureaucratic.sealHint")}
        </p>
      </div>
    </section>
  );
}
