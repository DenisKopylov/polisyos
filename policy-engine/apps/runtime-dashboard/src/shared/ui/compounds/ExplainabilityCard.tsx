import { useState, type ReactNode } from "react";
import type {
  PolicyDesignCaseProjectionBlocker,
  QuantityUncertainty,
  QuantityValueOutput,
} from "@polisyos/runtime-api-client";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Quantity } from "@/shared/ui/quantity";
import {
  authorityStatusBadgeProps,
  issueAuthorityCountPresentation,
} from "@/shared/ui/AuthorityStatusPresentation";
import { Badge, Button, Card } from "@polisyos/atlas-ui";

import { MethodologyBadge } from "./MethodologyBadge";
import { BlockerCard } from "./BlockerCard";
import { presentDecisionGradeLabel } from "./decisionGradePresentation";

export type ExplainabilityLevel = "glance" | "summary" | "deep";

export type ExplainabilityFactor = {
  label: string;
  value: string;
  direction: "positive" | "negative" | "neutral";
};

export type ExplainabilityVerdict = {
  confidence: QuantityValueOutput;
  decisionGrade?: string | null;
  summary?: string;
};

export type ExplainabilityGovernance = {
  passed: number;
  failed: number;
  warnings: number;
  blockers?: PolicyDesignCaseProjectionBlocker[];
};

type ExplainabilityCardProps = {
  level?: ExplainabilityLevel;
  verdict: ExplainabilityVerdict;
  methodology?: QuantityUncertainty["method"];
  keyFactors?: ExplainabilityFactor[];
  governance?: ExplainabilityGovernance;
  expandTo?: ExplainabilityLevel;
  onLevelChange?: (level: ExplainabilityLevel) => void;
  deepContent?: ReactNode;
  className?: string;
};

const DIRECTION_CLASS: Record<ExplainabilityFactor["direction"], string> = {
  positive: "text-[var(--color-chart-primary)]",
  negative: "text-[var(--color-chart-secondary)]",
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
  const decisionGrade = presentDecisionGradeLabel(verdict.decisionGrade);

  function setLevel(next: ExplainabilityLevel) {
    setInternalLevel(next);
    onLevelChange?.(next);
  }

  return (
    <Card
      className={cn("space-y-4", className)}
      data-decision-grade-presentation={decisionGrade.classification}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <Quantity
            format="percent"
            provenanceMode="off"
            value={verdict.confidence}
            variant="hero"
          />
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                data-decision-grade-presentation={decisionGrade.classification}
                data-owner-decision-grade={
                  decisionGrade.ownerLabel ?? undefined
                }
                kind="outline"
              >
                {decisionGrade.ownerLabel ?? t("common.unknown")}
              </Badge>
              <span className="text-muted text-xs">
                {decisionGrade.classification}
              </span>
              {methodology ? (
                <MethodologyBadge methodology={methodology} />
              ) : null}
            </div>
            {verdict.summary ? (
              <p className="text-muted max-w-lg text-sm leading-relaxed">
                {verdict.summary}
              </p>
            ) : null}
          </div>
        </div>
        {governance ? (
          <div className="flex items-center gap-2 text-xs font-semibold">
            <Badge
              {...authorityStatusBadgeProps(
                issueAuthorityCountPresentation("passed", governance.passed),
              )}
            >
              {t("shared.ui.explainabilityCard.countPassed", {
                count: governance.passed,
              })}
            </Badge>
            {governance.failed > 0 ? (
              <Badge
                {...authorityStatusBadgeProps(
                  issueAuthorityCountPresentation("failed", governance.failed),
                )}
              >
                {t("shared.ui.explainabilityCard.countFailed", {
                  count: governance.failed,
                })}
              </Badge>
            ) : null}
            {governance.warnings > 0 ? (
              <Badge
                {...authorityStatusBadgeProps(
                  issueAuthorityCountPresentation(
                    "warnings",
                    governance.warnings,
                  ),
                )}
              >
                {t("shared.ui.explainabilityCard.countWarnings", {
                  count: governance.warnings,
                })}
              </Badge>
            ) : null}
          </div>
        ) : null}
      </div>

      {(level === "summary" || level === "deep") && keyFactors.length > 0 ? (
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
      ) : null}

      {(level === "summary" || level === "deep") &&
      governance?.blockers?.length ? (
        <div className="space-y-3">
          <p className="text-sm font-semibold">
            {t("shared.ui.explainabilityCard.governanceBlockers")}
          </p>
          {governance.blockers.map((blocker) => (
            <BlockerCard
              blocker={blocker}
              key={`${blocker.code}:${blocker.message}`}
            />
          ))}
        </div>
      ) : null}

      {level === "deep" ? deepContent : null}

      {expandTo && level !== expandTo ? (
        <Button size="sm" variant="outline" onClick={() => setLevel(expandTo)}>
          {expandTo === "summary"
            ? t("shared.ui.explainabilityCard.showDetails")
            : t("shared.ui.explainabilityCard.fullAnalysis")}
        </Button>
      ) : null}
      {level !== "glance" ? (
        <Button size="sm" variant="link" onClick={() => setLevel("glance")}>
          {t("shared.ui.explainabilityCard.collapse")}
        </Button>
      ) : null}
    </Card>
  );
}
