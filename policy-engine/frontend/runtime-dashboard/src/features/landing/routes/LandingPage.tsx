import { RouteIconProvider } from "@/app/providers/RouteIconProvider";
import { useI18n } from "@/i18n/LocaleProvider";
import { SUPPORTED_LOCALES } from "@/i18n/locale";
import { HeroSection } from "../components/HeroSection";
import { CapabilitiesGrid } from "../components/CapabilitiesGrid";
import { HowItWorksTimeline } from "../components/HowItWorksTimeline";
import { CallToAction } from "../components/CallToAction";

export default function LandingPage() {
  const { locale, setLocale, t } = useI18n();

  return (
    <div className="min-h-screen bg-[var(--canvas)]">
      <RouteIconProvider surface="public" />
      <header className="flex items-center justify-between px-8 py-5">
        <span className="font-sans text-lg font-extrabold tracking-tight text-[var(--ink)]">
          PolicyOS
        </span>
        <div className="flex items-center gap-4">
          {SUPPORTED_LOCALES.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setLocale(value)}
              className="rounded-[var(--radius-pill)] px-3 py-1.5 text-xs font-bold tracking-wider text-[var(--slate)] uppercase transition hover:bg-white/50"
              data-active={locale === value}
            >
              {t(`common.locale.${value}`)}
            </button>
          ))}
        </div>
      </header>
      <main>
        <HeroSection />
        <CapabilitiesGrid />
        <HowItWorksTimeline />
        <CallToAction />
      </main>
      <footer className="border-t border-[var(--line)] px-8 py-8 text-center text-xs text-[var(--slate)]">
        PolicyOS
      </footer>
    </div>
  );
}
