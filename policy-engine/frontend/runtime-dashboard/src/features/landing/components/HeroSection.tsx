import { Button } from "@/shared/ui";
import { JanusGlyph } from "@/shared/brand/JanusGlyph";
import { useI18n } from "@/i18n/LocaleProvider";

export function HeroSection() {
  const { t } = useI18n();

  return (
    <section className="flex flex-col items-center gap-8 px-6 pt-24 pb-16 text-center">
      <JanusGlyph
        variant="mark"
        size={32}
        decorative
        className="mb-2 opacity-90"
      />
      <h1 className="font-sans text-[clamp(40px,6vw,56px)] leading-[1.08] font-extrabold tracking-[-0.04em] text-[var(--ink)]">
        {t("landing.heroTitle")}
      </h1>
      <p className="max-w-[640px] text-lg leading-relaxed text-[var(--slate)]">
        {t("landing.heroSubtitle")}
      </p>
      <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
        <Button variant="primary" size="lg" to="/login">
          {t("landing.heroCta")}
        </Button>
        <Button variant="ghost" size="lg" to="/?mode=clerk">
          {t("landing.heroExploreCta")}
        </Button>
      </div>
    </section>
  );
}
