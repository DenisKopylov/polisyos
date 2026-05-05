import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";

import { epistemicLabel } from "../../ast/epistemic-map";
import type { BureaucraticEpistemicSummary } from "../../ast/bureaucratic-document-ast";
import { EPISTEMIC_COLORS } from "./bureaucratic-tokens";

type EpistemicLegendProps = {
  summary: BureaucraticEpistemicSummary;
};

const ORDER = [
  "evidence_filled",
  "model_generated",
  "operator_filled",
  "imported",
] as const;

export function EpistemicLegend({ summary }: EpistemicLegendProps) {
  const { t } = useOptionalI18n();
  return (
    <section aria-labelledby="bureaucratic-epistemic-map" className="space-y-2">
      <h2 id="bureaucratic-epistemic-map" className="text-base font-semibold">
        {t("pages.artifacts.bureaucratic.epistemicLegend")}
      </h2>
      <dl className="grid gap-2 md:grid-cols-4">
        {ORDER.map((origin) => (
          <div
            key={origin}
            className={`rounded-md border p-2 ${EPISTEMIC_COLORS[origin]}`}
          >
            <dt className="text-xs font-semibold">{epistemicLabel(origin)}</dt>
            <dd className="mt-1 text-lg font-semibold">
              {Math.round((summary[origin] ?? 0) * 100)}%
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
