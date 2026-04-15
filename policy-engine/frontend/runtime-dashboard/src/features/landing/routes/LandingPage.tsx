import { useI18n } from "@/i18n/LocaleProvider";
import { HeroSection } from "../components/HeroSection";
import { CapabilitiesGrid } from "../components/CapabilitiesGrid";
import { HowItWorksTimeline } from "../components/HowItWorksTimeline";
import { CallToAction } from "../components/CallToAction";

export default function LandingPage() {
  const { locale, setLocale } = useI18n();

  return (
    <div className="min-h-screen bg-[var(--canvas)]">
      <header className="flex items-center justify-between px-8 py-5">
        <span className="font-sans text-lg font-extrabold tracking-tight text-[var(--ink)]">
          PolicyOS
        </span>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setLocale(locale === "en" ? "uk" : "en")}
            className="rounded-[var(--radius-pill)] px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-[var(--slate)] transition hover:bg-white/50"
          >
            {locale === "en" ? "UK" : "EN"}
          </button>
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
