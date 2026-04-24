import type { ReactNode } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { Badge, Card } from "@/shared/ui/primitives";
import type { BadgeKind } from "@/shared/ui/Badge";

export type BlockingType = string;

export type SuggestedExperiment = {
  id: string;
  description: string;
  rationale?: string;
  feasibility?: "low" | "medium" | "high";
};

type NegativeCertificateCardProps = {
  blockingType: BlockingType;
  reason: string;
  detail?: ReactNode;
  assumptions?: string[];
  suggestedExperiments?: SuggestedExperiment[];
  className?: string;
};

const FEASIBILITY_KIND: Record<string, BadgeKind> = {
  high: "ok",
  medium: "warn",
  low: "fail",
};

export function NegativeCertificateCard({
  blockingType,
  reason,
  detail,
  assumptions = [],
  suggestedExperiments = [],
  className,
}: NegativeCertificateCardProps) {
  const { t } = useI18n();
  const blockingLabels: Record<string, { label: string; kind: BadgeKind }> = {
    identification_failure: {
      kind: "fail",
      label: t(
        "shared.ui.negativeCertificateCard.blockingLabels.identificationFailure",
      ),
    },
    data_insufficient: {
      kind: "fail",
      label: t(
        "shared.ui.negativeCertificateCard.blockingLabels.dataInsufficient",
      ),
    },
    assumption_violation: {
      kind: "fail",
      label: t(
        "shared.ui.negativeCertificateCard.blockingLabels.assumptionViolation",
      ),
    },
    bounds_only: {
      kind: "warn",
      label: t("shared.ui.negativeCertificateCard.blockingLabels.boundsOnly"),
    },
    transport_failure: {
      kind: "warn",
      label: t(
        "shared.ui.negativeCertificateCard.blockingLabels.transportFailure",
      ),
    },
  };
  const blocking = blockingLabels[blockingType] ?? {
    label: blockingType,
    kind: "fail" as const,
  };

  return (
    <Card
      className={cn(
        "space-y-4 border-[var(--color-status-rejected)]/20",
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold">
            {t("shared.ui.negativeCertificateCard.title")}
          </h3>
          <p className="text-muted text-sm leading-relaxed">{reason}</p>
        </div>
        <Badge kind={blocking.kind}>{blocking.label}</Badge>
      </div>

      {detail && (
        <div className="border-line bg-surface/70 rounded-2xl border p-3 text-sm">
          {detail}
        </div>
      )}

      {assumptions.length > 0 && (
        <div>
          <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
            {t("shared.ui.negativeCertificateCard.assumptions")}
          </p>
          <ul className="space-y-1 text-sm">
            {assumptions.map((a) => (
              <li key={a} className="flex items-start gap-2">
                <span className="mt-1 text-[var(--color-status-rejected)]">
                  {"\u2717"}
                </span>
                <span>{a}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {suggestedExperiments.length > 0 && (
        <div>
          <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
            {t("shared.ui.negativeCertificateCard.suggestedExperiments")}
          </p>
          <div className="space-y-2">
            {suggestedExperiments.map((exp) => (
              <article
                key={exp.id}
                className="border-line bg-surface/70 rounded-2xl border p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium">{exp.description}</p>
                  {exp.feasibility && (
                    <Badge
                      kind={FEASIBILITY_KIND[exp.feasibility] ?? "neutral"}
                    >
                      {t(
                        `shared.ui.negativeCertificateCard.feasibility.${exp.feasibility}`,
                      )}
                    </Badge>
                  )}
                </div>
                {exp.rationale && (
                  <p className="text-muted mt-1 text-xs">{exp.rationale}</p>
                )}
              </article>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
