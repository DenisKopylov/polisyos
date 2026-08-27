import { useEffect, useState } from "react";

import { AccessibilityEvidence } from "../components/AccessibilityEvidence";
import { ClaimPostureRegister } from "../components/ClaimPostureRegister";
import { PostureMethodology } from "../components/PostureMethodology";
import { loadPosture, type PostureLoadResult } from "../domain/loadPosture";
import type { ClaimPostureAudience } from "../domain/posture";
import { downloadTrustPostureMachine } from "../export/trustPostureTwin";
import { useI18n } from "@/shared/i18n/LocaleProvider";

type HumanAudience = Exclude<ClaimPostureAudience, "MACHINE">;
const HUMAN_AUDIENCES: readonly HumanAudience[] = [
  "PUBLIC",
  "REVIEWER",
  "EXPERT",
];

/** Public, artifact-backed trust posture route. */
export default function TrustPosturePage() {
  const { t } = useI18n();
  const [audience, setAudience] = useState<HumanAudience>("PUBLIC");
  const [result, setResult] = useState<PostureLoadResult | null>(null);

  useEffect(() => {
    let current = true;
    void loadPosture().then((loaded) => {
      if (current) setResult(loaded);
    });
    return () => {
      current = false;
    };
  }, []);

  return (
    <div
      className="min-h-screen bg-[var(--canvas)] px-4 py-8 text-[var(--ink)] sm:px-8"
      data-testid="trust-posture-page"
    >
      <div className="mx-auto max-w-6xl">
        <header className="rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--paper)] p-6">
          <p className="text-xs font-semibold tracking-[0.2em] text-[var(--slate)] uppercase">
            {t("trust.eyebrow")}
          </p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight">
            {t("trust.title")}
          </h1>
          <p className="mt-3 max-w-3xl text-sm text-[var(--slate)]">
            {t("trust.pageFrame")}
          </p>
        </header>

        {result === null ? (
          <p className="mt-6" aria-live="polite" role="status">
            {t("trust.loading")}
          </p>
        ) : null}

        {result?.status === "unavailable" ? (
          <section
            className="mt-6 rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--paper)] p-6"
            data-testid="trust-posture-unavailable"
            role="status"
          >
            <h2 className="text-xl font-bold">{t("trust.unavailableTitle")}</h2>
            <p className="mt-2 text-sm text-[var(--slate)]">
              {t("trust.unavailableFrame")}
            </p>
          </section>
        ) : null}

        {result?.status === "available" ? (
          <div className="mt-6 space-y-6">
            <div className="flex flex-wrap items-end justify-between gap-4 rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--paper)] p-4">
              <div
                aria-label={t("trust.detailControlLabel")}
                className="flex flex-wrap gap-2"
                role="group"
              >
                {HUMAN_AUDIENCES.map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={audience === value}
                    className="rounded-[var(--radius-pill)] border border-[var(--line)] px-3 py-2 text-sm font-semibold"
                    onClick={() => setAudience(value)}
                  >
                    {t(`trust.audience.${value}`)}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="rounded-[var(--radius-pill)] border border-[var(--line)] px-3 py-2 text-sm font-semibold"
                onClick={() => downloadTrustPostureMachine(result.rawBytes)}
              >
                {t("trust.downloadMachine")}
              </button>
            </div>

            <ClaimPostureRegister
              audience={audience}
              register={result.register}
            />
            <PostureMethodology audience={audience} register={result.register} />
            <AccessibilityEvidence register={result.register} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
