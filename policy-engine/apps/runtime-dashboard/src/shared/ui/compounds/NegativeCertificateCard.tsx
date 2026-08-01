import type { ReactNode } from "react";
import type { PolicyDesignCaseProjectionBlocker } from "@polisyos/runtime-api-client";

import { Glyph } from "@/shared/brand/Glyph";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Badge, Card, EvidenceLink } from "@polisyos/atlas-ui";

const MODULE_LABEL = "Module";
const NEXT_ACTION_LABEL = "Next action";

export type SuggestedExperiment = {
  id: string;
  description: string;
  rationale?: string;
  feasibility?: string;
};

type NegativeCertificateCardProps = {
  blocker: PolicyDesignCaseProjectionBlocker;
  detail?: ReactNode;
  assumptions?: string[];
  suggestedExperiments?: SuggestedExperiment[];
  className?: string;
};

function evidenceHref(reference: string) {
  return reference.startsWith("https://") ||
    reference.startsWith("http://") ||
    reference.startsWith("/")
    ? reference
    : undefined;
}

/** Renders a producer-issued projection blocker without local classification. */
export function NegativeCertificateCard({
  blocker,
  detail,
  assumptions = [],
  suggestedExperiments = [],
  className,
}: NegativeCertificateCardProps) {
  const { t } = useI18n();
  return (
    <Card
      className={cn(
        "space-y-4 border-[var(--color-status-rejected)]/20",
        className,
      )}
      data-producer-blocker-code={blocker.code}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold">
            {t("shared.ui.negativeCertificateCard.title")}
          </h3>
          <p className="text-muted text-sm leading-relaxed">
            {blocker.message}
          </p>
        </div>
        <Badge kind="fail">{blocker.code}</Badge>
      </div>

      <dl className="border-line bg-surface/70 grid gap-3 rounded-2xl border p-3 text-sm sm:grid-cols-2">
        {blocker.severity ? (
          <div>
            <dt className="text-muted text-xs font-semibold uppercase">
              {t("pages.composer.severity")}
            </dt>
            <dd
              data-authority-presentation="opaque"
              data-owner-severity={blocker.severity}
            >
              {blocker.severity}
            </dd>
          </div>
        ) : null}
        {blocker.owner ? (
          <div>
            <dt className="text-muted text-xs font-semibold uppercase">
              {t("operatorDiagnostic.owner")}
            </dt>
            <dd>{blocker.owner}</dd>
          </div>
        ) : null}
        {blocker.module_id ? (
          <div>
            <dt className="text-muted text-xs font-semibold uppercase">
              {MODULE_LABEL}
            </dt>
            <dd>{blocker.module_id}</dd>
          </div>
        ) : null}
        {blocker.next_action ? (
          <div>
            <dt className="text-muted text-xs font-semibold uppercase">
              {NEXT_ACTION_LABEL}
            </dt>
            <dd>{blocker.next_action}</dd>
          </div>
        ) : null}
        {blocker.evidence_ref ? (
          <div className="sm:col-span-2">
            <dt className="text-muted text-xs font-semibold uppercase">
              {t("pages.runs.evidence")}
            </dt>
            <dd>
              {evidenceHref(blocker.evidence_ref) ? (
                <EvidenceLink
                  evidenceRef={blocker.evidence_ref}
                  href={evidenceHref(blocker.evidence_ref)!}
                />
              ) : (
                <EvidenceLink evidenceRef={blocker.evidence_ref} />
              )}
            </dd>
          </div>
        ) : null}
      </dl>

      {detail ? (
        <div className="border-line bg-surface/70 rounded-2xl border p-3 text-sm">
          {detail}
        </div>
      ) : null}

      {assumptions.length > 0 ? (
        <div>
          <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
            {t("shared.ui.negativeCertificateCard.assumptions")}
          </p>
          <ul className="space-y-1 text-sm">
            {assumptions.map((assumption) => (
              <li key={assumption} className="flex items-start gap-2">
                <Glyph
                  className="text-muted mt-1 shrink-0"
                  decorative
                  name="blocker"
                  size={12}
                />
                <span>{assumption}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {suggestedExperiments.length > 0 ? (
        <div data-authority-posture="candidate">
          <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
            {t("shared.ui.negativeCertificateCard.suggestedExperiments")}
          </p>
          <div className="space-y-2">
            {suggestedExperiments.map((experiment) => (
              <article
                key={experiment.id}
                className="border-line bg-surface/70 rounded-2xl border border-dashed p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium">
                    {experiment.description}
                  </p>
                  {experiment.feasibility ? (
                    <Badge kind="outline">{experiment.feasibility}</Badge>
                  ) : null}
                </div>
                {experiment.rationale ? (
                  <p className="text-muted mt-1 text-xs">
                    {experiment.rationale}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  );
}
