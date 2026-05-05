import { useI18n } from "@/shared/i18n/LocaleProvider";

const STEPS = [
  {
    labelKey: "landing.stepQuestion",
    descriptionKey: "landing.stepQuestionDescription",
    number: 1,
  },
  {
    labelKey: "landing.stepAnalysis",
    descriptionKey: "landing.stepAnalysisDescription",
    number: 2,
  },
  {
    labelKey: "landing.stepEvidence",
    descriptionKey: "landing.stepEvidenceDescription",
    number: 3,
  },
  {
    labelKey: "landing.stepDecision",
    descriptionKey: "landing.stepDecisionDescription",
    number: 4,
  },
] as const;

export function HowItWorksTimeline() {
  const { t } = useI18n();

  return (
    <section className="px-6 py-16">
      <h2 className="mb-12 text-center text-2xl font-bold tracking-tight text-[var(--ink)]">
        {t("landing.howItWorksTitle")}
      </h2>
      <div className="mx-auto grid max-w-[960px] grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step, i) => (
          <div
            key={step.labelKey}
            className="flex flex-col items-center gap-4 text-center"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[linear-gradient(135deg,var(--button-primary-start),var(--button-primary-end))] text-lg font-extrabold text-[var(--button-primary-text)]">
              {step.number}
            </div>
            {i < STEPS.length - 1 && (
              <div
                className="hidden h-px w-full bg-[var(--line)] lg:block"
                aria-hidden
              />
            )}
            <h3 className="text-base font-bold text-[var(--ink)]">
              {t(step.labelKey)}
            </h3>
            <p className="text-sm leading-relaxed text-[var(--slate)]">
              {t(step.descriptionKey)}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
