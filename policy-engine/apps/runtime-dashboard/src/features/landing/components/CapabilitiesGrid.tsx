import { useI18n } from "@/shared/i18n/LocaleProvider";

const CAPABILITIES = [
  {
    titleKey: "landing.causalAnalysis.title",
    descriptionKey: "landing.causalAnalysis.description",
    icon: (
      <svg
        className="h-8 w-8 text-[var(--teal)]"
        fill="none"
        viewBox="0 0 32 32"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <circle cx="8" cy="16" r="4" />
        <circle cx="24" cy="8" r="4" />
        <circle cx="24" cy="24" r="4" />
        <path d="M12 14l8-4M12 18l8 4" />
      </svg>
    ),
  },
  {
    titleKey: "landing.policySimulation.title",
    descriptionKey: "landing.policySimulation.description",
    icon: (
      <svg
        className="h-8 w-8 text-[var(--teal)]"
        fill="none"
        viewBox="0 0 32 32"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <rect x="4" y="4" width="24" height="24" rx="4" />
        <path d="M8 20l4-6 4 4 4-8 4 6" />
      </svg>
    ),
  },
  {
    titleKey: "landing.dataFabric.title",
    descriptionKey: "landing.dataFabric.description",
    icon: (
      <svg
        className="h-8 w-8 text-[var(--teal)]"
        fill="none"
        viewBox="0 0 32 32"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <ellipse cx="16" cy="10" rx="10" ry="4" />
        <path d="M6 10v6c0 2.2 4.5 4 10 4s10-1.8 10-4v-6" />
        <path d="M6 16v6c0 2.2 4.5 4 10 4s10-1.8 10-4v-6" />
      </svg>
    ),
  },
  {
    titleKey: "landing.governanceEngine.title",
    descriptionKey: "landing.governanceEngine.description",
    icon: (
      <svg
        className="h-8 w-8 text-[var(--teal)]"
        fill="none"
        viewBox="0 0 32 32"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path d="M16 4l10 5v8c0 5.5-4.3 10.5-10 12C10.3 27.5 6 22.5 6 17V9l10-5z" />
        <path d="M12 16l3 3 5-6" />
      </svg>
    ),
  },
] as const;

export function CapabilitiesGrid() {
  const { t } = useI18n();

  return (
    <section className="px-6 py-16">
      <h2 className="mb-10 text-center text-2xl font-bold tracking-tight text-[var(--ink)]">
        {t("landing.capabilitiesTitle")}
      </h2>
      <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 sm:grid-cols-2">
        {CAPABILITIES.map((cap) => (
          <article
            key={cap.titleKey}
            className="panel flex flex-col gap-4 rounded-[var(--radius-panel)] p-8"
          >
            {cap.icon}
            <h3 className="text-lg font-bold text-[var(--ink)]">
              {t(cap.titleKey)}
            </h3>
            <p className="text-sm leading-relaxed text-[var(--slate)]">
              {t(cap.descriptionKey)}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
