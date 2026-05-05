import { useState, type ReactNode } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Badge, Button, Card } from "@/shared/ui/primitives";
import type { BadgeKind } from "@/shared/ui/Badge";
import { ConfidenceGauge } from "@/shared/charts";

export type ExplainabilityLevel = "glance" | "summary" | "deep";

export type ExplainabilityFactor = {
  label: string;
  value: string;
  direction: "positive" | "negative" | "neutral";
};

export type ExplainabilityVerdict = {
  status: "approved" | "rejected" | "review";
  confidence: number;
  summary?: string;
};

export type ExplainabilityGovernance = {
  passed: number;
  failed: number;
  warnings: number;
  blockers?: string[];
};

type ExplainabilityCardProps = {
  level?: ExplainabilityLevel;
  verdict: ExplainabilityVerdict;
  methodology?: string;
  keyFactors?: ExplainabilityFactor[];
  governance?: ExplainabilityGovernance;
  expandTo?: ExplainabilityLevel;
  onLevelChange?: (level: ExplainabilityLevel) => void;
  deepContent?: ReactNode;
  className?: string;
};

const VERDICT_KIND: Record<ExplainabilityVerdict["status"], BadgeKind> = {
  approved: "ok",
  rejected: "fail",
  review: "warn",
};

const DIRECTION_CLASS: Record<ExplainabilityFactor["direction"], string> = {
  positive: "text-[var(--color-status-approved)]",
  negative: "text-[var(--color-status-rejected)]",
  neutral: "text-muted",
};

const DIRECTION_ICON: Record<ExplainabilityFactor["direction"], string> = {
  positive: "\u2191",
  negative: "\u2193",
  neutral: "\u2022",
};

export function ExplainabilityCard({
  level: controlledLevel,
  verdict,
  methodology,
  keyFactors = [],
  governance,
  expandTo,
  onLevelChange,
  deepContent,
  className,
}: ExplainabilityCardProps) {
  const { t } = useI18n();
  const [internalLevel, setInternalLevel] =
    useState<ExplainabilityLevel>("glance");
  const level = controlledLevel ?? internalLevel;
  const verdictLabels: Record<ExplainabilityVerdict["status"], string> = {
    approved: t("shared.ui.explainabilityCard.verdict.approved"),
    rejected: t("shared.ui.explainabilityCard.verdict.rejected"),
    review: t("shared.ui.explainabilityCard.verdict.review"),
  };

  function setLevel(next: ExplainabilityLevel) {
    setInternalLevel(next);
    onLevelChange?.(next);
  }

  const total = governance
    ? governance.passed + governance.failed + governance.warnings
    : 0;

  return (
    <Card className={cn("space-y-4", className)}>
      {/* ── Glance: always visible ── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <ConfidenceGauge value={verdict.confidence} size={72} />
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Badge kind={VERDICT_KIND[verdict.status]}>
                {verdictLabels[verdict.status]}
              </Badge>
              {methodology && (
                <span className="text-muted font-mono text-xs">
                  {methodology}
                </span>
              )}
            </div>
            {verdict.summary && (
              <p className="text-muted max-w-lg text-sm leading-relaxed">
                {verdict.summary}
              </p>
            )}
          </div>
        </div>
        {governance && (
          <div className="flex items-center gap-2 text-xs font-semibold">
            <Badge kind="ok">
              {t("shared.ui.explainabilityCard.countPassed", {
                count: governance.passed,
              })}
            </Badge>
            {governance.failed > 0 && (
              <Badge kind="fail">
                {t("shared.ui.explainabilityCard.countFailed", {
                  count: governance.failed,
                })}
              </Badge>
            )}
            {governance.warnings > 0 && (
              <Badge kind="warn">
                {t("shared.ui.explainabilityCard.countWarnings", {
                  count: governance.warnings,
                })}
              </Badge>
            )}
          </div>
        )}
      </div>

      {/* ── Summary: key factors + governance ── */}
      {(level === "summary" || level === "deep") && keyFactors.length > 0 && (
        <div className="border-line rounded-2xl border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-line border-b">
                <th className="text-muted px-4 py-2 text-start text-xs font-medium uppercase">
                  {t("shared.ui.explainabilityCard.columns.factor")}
                </th>
                <th className="text-muted px-4 py-2 text-end text-xs font-medium uppercase">
                  {t("shared.ui.explainabilityCard.columns.value")}
                </th>
              </tr>
            </thead>
            <tbody>
              {keyFactors.map((factor) => (
                <tr
                  key={factor.label}
                  className="border-line border-b last:border-0"
                >
                  <td className="px-4 py-2.5 font-medium">{factor.label}</td>
                  <td
                    className={cn(
                      "px-4 py-2.5 text-end font-semibold",
                      DIRECTION_CLASS[factor.direction],
                    )}
                  >
                    <span className="mr-1">
                      {DIRECTION_ICON[factor.direction]}
                    </span>
                    {factor.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(level === "summary" || level === "deep") &&
        governance &&
        governance.blockers &&
        governance.blockers.length > 0 && (
          <div className="rounded-2xl bg-[color-mix(in_srgb,var(--color-status-rejected)_8%,transparent)] p-3">
            <p className="text-sm font-semibold text-[var(--color-status-rejected)]">
              {t("shared.ui.explainabilityCard.governanceBlockers")}
            </p>
            <ul className="text-muted mt-1 list-inside list-disc text-sm">
              {governance.blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </div>
        )}

      {/* ── Deep: extended content slot ── */}
      {level === "deep" && deepContent}

      {/* ── Expand button ── */}
      {expandTo && level !== expandTo && (
        <Button size="sm" variant="outline" onClick={() => setLevel(expandTo)}>
          {expandTo === "summary"
            ? t("shared.ui.explainabilityCard.showDetails")
            : t("shared.ui.explainabilityCard.fullAnalysis")}
        </Button>
      )}
      {level !== "glance" && (
        <Button size="sm" variant="link" onClick={() => setLevel("glance")}>
          {t("shared.ui.explainabilityCard.collapse")}
        </Button>
      )}
    </Card>
  );
}
