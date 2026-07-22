import type { ReactNode } from "react";

import {
  Badge,
  Card,
  EnvelopeChip,
  governedAuthorityPurposePresentation,
  type GovernedAuthorityPurpose,
} from "@polisyos/atlas-ui";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import { presentDecisionGradeLabel } from "./decisionGradePresentation";

export type DecisionCardDiagnostic = {
  /** Opaque owner label; it never selects authority clothing. */
  kind?: string | null;
  label: string;
};

type DecisionCardProps = {
  authorityPurpose?: GovernedAuthorityPurpose;
  title: string;
  subtitle?: ReactNode;
  verdict: string | null;
  confidence?: ReactNode;
  summary?: ReactNode;
  diagnostics?: DecisionCardDiagnostic[];
  meta?: Array<{
    label: string;
    value: ReactNode;
  }>;
  eyebrow?: ReactNode;
  sigil?: ReactNode;
  children?: ReactNode;
};

export function DecisionCard({
  authorityPurpose,
  children,
  confidence,
  diagnostics = [],
  eyebrow,
  meta = [],
  sigil,
  subtitle,
  summary,
  title,
  verdict,
}: DecisionCardProps) {
  const { t } = useI18n();
  const authorityPresentation = authorityPurpose
    ? governedAuthorityPurposePresentation(authorityPurpose)
    : null;
  const fixtureOnly =
    authorityPresentation?.fixtureAuthority === "fixture_only";
  const governed = Boolean(authorityPurpose) && !fixtureOnly;
  const authorityPosture = fixtureOnly
    ? "fixture-only"
    : governed
      ? "governed-authority"
      : "candidate";
  const decisionGrade = presentDecisionGradeLabel(verdict);

  return (
    <Card
      className={cn(
        "space-y-4",
        governed
          ? "border-solid border-[var(--color-transport-live)]/40"
          : "border-dashed border-[var(--teal)]/45",
      )}
      data-authority-posture={authorityPosture}
      data-fixture-authority={authorityPresentation?.fixtureAuthority}
      data-decision-grade-presentation={decisionGrade.classification}
      data-testid={`decision-card-${fixtureOnly ? "fixture" : governed ? "governed" : "candidate"}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          {eyebrow ? <div className="mb-1">{eyebrow}</div> : null}
          <h3 className="text-lg font-semibold">{title}</h3>
          {subtitle ? (
            <div className="text-muted text-sm">{subtitle}</div>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {sigil ? <div className="mr-1 shrink-0">{sigil}</div> : null}
          {authorityPurpose ? (
            <EnvelopeChip authorityPurpose={authorityPurpose} />
          ) : (
            <Badge kind="outline">
              {t("pages.artifacts.metricValidation.columns.candidate")}
            </Badge>
          )}
          <Badge
            data-decision-grade-presentation={decisionGrade.classification}
            data-owner-decision-grade={decisionGrade.ownerLabel ?? undefined}
            kind="outline"
          >
            {decisionGrade.ownerLabel ?? "unknown"}
          </Badge>
          {confidence ? <Badge kind="outline">{confidence}</Badge> : null}
        </div>
      </div>

      {summary ? (
        <div className="border-line bg-surface/70 text-muted rounded-2xl border p-3 text-sm">
          {summary}
        </div>
      ) : null}

      {diagnostics.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {diagnostics.map((diagnostic) => (
            <Badge
              key={`${diagnostic.kind ?? "neutral"}-${diagnostic.label}`}
              data-owner-diagnostic-kind={diagnostic.kind ?? undefined}
              kind="outline"
            >
              {diagnostic.label}
            </Badge>
          ))}
        </div>
      ) : null}

      {meta.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {meta.map((item) => (
            <div
              key={item.label}
              className="border-line bg-canvas/30 rounded-2xl border p-3 text-sm"
            >
              <p className="text-muted text-xs tracking-wide uppercase">
                {item.label}
              </p>
              <div className="mt-2 font-semibold">{item.value}</div>
            </div>
          ))}
        </div>
      ) : null}

      {children}
    </Card>
  );
}
