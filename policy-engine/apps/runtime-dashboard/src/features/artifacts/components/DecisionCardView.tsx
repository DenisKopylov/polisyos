import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import MetricValidationComparisonTable from "@/features/artifacts/components/MetricValidationComparisonTable";
import type { ArtifactView } from "@/features/artifacts/domain/searchParams";
import {
  MonographLayout,
  buildDecisionPacketDocument,
} from "@/features/artifacts/reading-view/MonographLayout";
import { ReadingViewToggle } from "@/features/artifacts/reading-view/ReadingViewToggle";
import { useFeatureFlag } from "@/app/providers/FeatureFlagProvider";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import type { BadgeKind } from "@/shared/ui";
import {
  Button,
  DecisionCard,
  ProvenanceStrip,
  Select,
  chartTheme,
} from "@/shared/ui";
import { UncertaintyBand } from "@/shared/charts";
import { EvidenceSigil } from "@/shared/brand/EvidenceSigil";
import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";
import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import { parseDecisionCardPayload } from "@/shared/lib/domain/decision";
import { useGlobalShortcut } from "@/shared/lib/hooks/useKeyboardShortcuts";
import { formatDate, formatDuration } from "@/shared/lib/utils";
import { triggerPrint } from "@/shared/export/printExport";

type DecisionCardViewProps = {
  payload: unknown;
  artifactKind: string;
  viewMode?: ArtifactView;
  onViewModeChange?: (nextViewMode: ArtifactView) => void;
};

type Translate = ReturnType<typeof useI18n>["t"];

function verdictKind(verdict: DecisionCardViewModel["verdict"]) {
  if (verdict === "APPROVE") {
    return "ok" as const;
  }
  if (verdict === "REJECT") {
    return "fail" as const;
  }
  return "warn" as const;
}

function confidenceKind(confidence: DecisionCardViewModel["confidence"]) {
  if (confidence === "HIGH") {
    return "ok" as const;
  }
  if (confidence === "LOW") {
    return "fail" as const;
  }
  return "warn" as const;
}

function diagnosticBadgeKind(
  kind: DecisionCardViewModel["diagnosticsBadges"][number]["kind"],
): BadgeKind {
  if (kind === "ok" || kind === "warn" || kind === "fail") {
    return kind;
  }
  return "neutral";
}

function decisionEyebrowItems(
  card: DecisionCardViewModel,
  t: Translate,
): ProvenanceItem[] {
  const items: ProvenanceItem[] = [
    {
      id: "intervention",
      glyph: "intervention",
      label: t("pages.artifacts.decisionCard.eyebrowInterventions", {
        count: card.interventionCount,
      }),
    },
  ];
  if (card.issues.blockerCount > 0) {
    items.push({
      id: "governance",
      glyph: "blocker",
      label: t("pages.artifacts.decisionCard.eyebrowBlocked"),
      intent: "blocked",
    });
  } else {
    items.push({
      id: "governance",
      glyph: "governance-pass",
      label: t("pages.artifacts.decisionCard.eyebrowGovernancePass"),
      intent: "verified",
    });
  }
  items.push({
    id: "evidence",
    glyph: "evidence",
    label:
      card.confidence === "HIGH"
        ? t("pages.artifacts.decisionCard.eyebrowStrongEvidence")
        : t("pages.artifacts.decisionCard.eyebrowWeakEvidence"),
    intent: card.confidence === "HIGH" ? "verified" : "pending",
    strokeStyle: card.confidence === "HIGH" ? "solid" : "dashed",
  });
  return items;
}

function identifiabilityFromConfidence(
  confidence: DecisionCardViewModel["confidence"],
): number {
  if (confidence === "HIGH") return 0.85;
  if (confidence === "LOW") return 0.25;
  return 0.55;
}

function bundleHashFromCard(card: DecisionCardViewModel): string {
  const seed = `${card.runId}:${card.sourceKind}:${card.generatedAt ?? ""}`;
  let hash = 0n;
  for (const ch of seed) {
    hash = (hash * 131n + BigInt(ch.codePointAt(0) ?? 0)) & 0xffffffffffffffffn;
  }
  return hash.toString(16).padStart(16, "0");
}

function uncertaintyBands(metric: DecisionCardViewModel["keyMetrics"][number]) {
  if (metric.ciLower === null || metric.ciUpper === null) {
    return [];
  }
  return [
    {
      lower: metric.ciLower,
      upper: metric.ciUpper,
      level: metric.ciLevel ?? 0.95,
    },
  ];
}

export default function DecisionCardView({
  payload,
  artifactKind,
  viewMode,
  onViewModeChange,
}: DecisionCardViewProps) {
  const { t } = useI18n();
  const narrativeViewEnabled = useFeatureFlag("enableNarrativeView");
  const card = useMemo(() => parseDecisionCardPayload(payload), [payload]);
  const readingDocument = useMemo(
    () => buildDecisionPacketDocument(payload),
    [payload],
  );
  const [localViewMode, setLocalViewMode] = useState<ArtifactView>("default");
  const [selectedBreakdown, setSelectedBreakdown] = useState<string>(
    card?.distributional?.breakdowns[0]?.dimensionLabel ?? "",
  );
  const printButtonRef = useRef<HTMLButtonElement | null>(null);
  const resolvedViewMode = viewMode ?? localViewMode;
  const isReadingView = resolvedViewMode === "reading";

  const canUseReadingView =
    narrativeViewEnabled &&
    artifactKind === "scientist.decision_packet" &&
    readingDocument !== null;

  function setReadingViewMode(nextViewMode: ArtifactView) {
    if (viewMode === undefined) {
      setLocalViewMode(nextViewMode);
    }
    onViewModeChange?.(nextViewMode);
  }

  useEffect(() => {
    if (!canUseReadingView && isReadingView) {
      setReadingViewMode("default");
    }
  }, [canUseReadingView, isReadingView]);

  useEffect(() => {
    if (isReadingView) {
      printButtonRef.current?.focus();
    }
  }, [isReadingView]);

  useGlobalShortcut(
    "decision-reading-view",
    { key: "r" },
    t("pages.artifacts.decisionCard.readingViewShortcut"),
    () => {
      if (!canUseReadingView) {
        return;
      }
      startTransition(() => {
        setReadingViewMode(isReadingView ? "default" : "reading");
      });
    },
    {
      enabled: canUseReadingView,
      group: t("pages.artifacts.decisionCard.readingViewShortcutGroup"),
    },
  );

  const activeBreakdown = useMemo(() => {
    const breakdowns = card?.distributional?.breakdowns ?? [];
    if (breakdowns.length === 0) {
      return null;
    }
    if (!selectedBreakdown) {
      return breakdowns[0];
    }
    return (
      breakdowns.find((item) => item.dimensionLabel === selectedBreakdown) ??
      breakdowns[0]
    );
  }, [card?.distributional?.breakdowns, selectedBreakdown]);

  if (!card) {
    return (
      <div className="bg-canvas/30 border-line rounded-xl border border-dashed p-4">
        <h3 className="mb-1 text-lg font-semibold">
          {t("pages.artifacts.decisionCard.title")}
        </h3>
        <p className="text-muted text-sm">
          {t("pages.artifacts.decisionCard.parseError", { artifactKind })}
        </p>
      </div>
    );
  }

  const printTargetId = `decision-packet-viewer-${card.runId.replace(/[^a-z0-9_-]+/gi, "-")}`;

  const actions = canUseReadingView ? (
    <div className="reading-view-toggle sticky top-4 z-[var(--z-sticky)] ml-auto flex w-fit items-center gap-2 print:hidden">
      <Button
        ref={printButtonRef}
        size="sm"
        type="button"
        variant="ghost"
        onClick={() =>
          triggerPrint({
            contentSelector: `#${printTargetId}`,
            includeTimestamp: true,
            title: t("pages.artifacts.decisionCard.printTitle", {
              runId: card.runId,
            }),
          })
        }
      >
        {t("pages.runs.report.printPdf")}
      </Button>
      <ReadingViewToggle
        onPressedChange={(nextPressed) => {
          startTransition(() => {
            setReadingViewMode(nextPressed ? "reading" : "default");
          });
        }}
        pressed={isReadingView}
      />
    </div>
  ) : null;

  if (canUseReadingView && isReadingView && readingDocument) {
    return (
      <div className="space-y-4" id={printTargetId}>
        {actions}
        <MonographLayout document={readingDocument} />
      </div>
    );
  }

  return (
    <div className="space-y-3" id={printTargetId}>
      {actions}
      <DecisionCard
        title={t("pages.artifacts.decisionCard.runTitle", {
          runId: card.runId,
        })}
        subtitle={
          <>
            <span>
              {t("pages.artifacts.decisionCard.subtitle", {
                sourceKind: card.sourceKind,
              })}
            </span>
            <span className="text-muted mx-2">·</span>
            <span>
              {t("pages.artifacts.decisionCard.generatedAt", {
                date: formatDate(card.generatedAt),
              })}
            </span>
          </>
        }
        eyebrow={
          <ProvenanceStrip
            title={t("pages.artifacts.decisionCard.eyebrowTitle")}
            items={decisionEyebrowItems(card, t)}
            density="compact"
          />
        }
        sigil={
          <EvidenceSigil
            bundleHash={bundleHashFromCard(card)}
            frescProfile={
              card.confidence === "HIGH"
                ? "replicated"
                : card.confidence === "LOW"
                  ? "reconnaissance"
                  : "corroborated"
            }
            identifiability={identifiabilityFromConfidence(card.confidence)}
            size={48}
          />
        }
        verdict={card.verdict}
        verdictKind={verdictKind(card.verdict)}
        confidence={`confidence:${card.confidence}`}
        confidenceKind={confidenceKind(card.confidence)}
        summary={card.policySummary}
        diagnostics={card.diagnosticsBadges.map((badge) => ({
          kind: diagnosticBadgeKind(badge.kind),
          label: badge.label,
        }))}
        meta={[
          {
            label: t("pages.artifacts.decisionCard.metaInterventions"),
            value: card.interventionCount,
          },
          {
            label: t("pages.artifacts.decisionCard.metaIssues"),
            value: t("pages.artifacts.decisionCard.metaIssuesSummary", {
              blockers: card.issues.blockerCount,
              info: card.issues.infoCount,
              warnings: card.issues.warningCount,
            }),
          },
          {
            label: t("pages.artifacts.decisionCard.metaBlockedPasses"),
            value:
              card.issues.blockedPasses.length > 0
                ? card.issues.blockedPasses.join(", ")
                : "-",
          },
          {
            label: t("pages.artifacts.decisionCard.metaDuration"),
            value: formatDuration(card.totalDurationMs),
          },
        ]}
      />

      <section className="border-line bg-panel rounded-xl border p-4">
        <h4 className="mb-2 text-base font-semibold">
          {t("pages.artifacts.decisionCard.keyMetrics")}
        </h4>
        {card.keyMetrics.length > 0 ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {card.keyMetrics.map((metric) => (
              <article
                key={metric.name}
                className="bg-canvas/30 border-line rounded-lg border p-2 text-sm"
              >
                <p className="text-muted text-xs uppercase">{metric.name}</p>
                <p className="font-semibold">
                  {metric.formatted}
                  {metric.unit ? ` ${metric.unit}` : ""}
                </p>
                {metric.ciLower !== null && metric.ciUpper !== null ? (
                  <p className="text-muted text-xs">
                    [{metric.ciLower.toFixed(2)}, {metric.ciUpper.toFixed(2)}]
                    {metric.ciLevel !== null
                      ? ` @ ${(metric.ciLevel * 100).toFixed(0)}%`
                      : ""}
                  </p>
                ) : null}
                {uncertaintyBands(metric).length > 0 ? (
                  <UncertaintyBand
                    estimate={metric.value}
                    bands={uncertaintyBands(metric)}
                    label={t("pages.artifacts.decisionCard.intervalLabel", {
                      metric: metric.name,
                    })}
                    unit={metric.unit ? ` ${metric.unit}` : ""}
                    disputed={Boolean(metric.assumptionWarnings?.length)}
                    identifiability={
                      metric.assumptionWarnings?.length
                        ? "estimated"
                        : "identified"
                    }
                    className="mt-3"
                    height={78}
                  />
                ) : null}
                {metric.testLabel ||
                metric.pValue != null ||
                metric.pAdj != null ? (
                  <p className="text-muted text-xs">
                    {metric.testLabel ??
                      t("pages.artifacts.decisionCard.statTest")}
                    {metric.pAdj != null
                      ? `, p_adj=${metric.pAdj.toFixed(4)}`
                      : metric.pValue != null
                        ? `, p=${metric.pValue.toFixed(4)}`
                        : ""}
                    {metric.significant != null
                      ? metric.significant
                        ? `, ${t("pages.artifacts.decisionCard.significant")}`
                        : `, ${t("pages.artifacts.decisionCard.notSignificant")}`
                      : ""}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="text-muted text-sm">
            {t("pages.artifacts.decisionCard.emptyMetrics")}
          </p>
        )}
      </section>

      <MetricValidationComparisonTable
        title={t("pages.artifacts.decisionCard.metricValidation")}
        comparisons={card.metricComparisons}
        familyAdjustment={card.metricValidationFamilyAdjustment}
      />

      {card.distributional ? (
        <section className="border-line bg-panel rounded-xl border p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-base font-semibold">
              {t("pages.artifacts.decisionCard.distributionalImpact")}
            </h4>
            {card.distributional.breakdowns.length > 1 ? (
              <Select
                value={activeBreakdown?.dimensionLabel ?? ""}
                onChange={(event) => setSelectedBreakdown(event.target.value)}
                className="w-auto rounded-lg px-2 py-1"
              >
                {card.distributional.breakdowns.map((breakdown) => (
                  <option
                    key={breakdown.dimensionLabel}
                    value={breakdown.dimensionLabel}
                  >
                    {breakdown.dimensionLabel}
                  </option>
                ))}
              </Select>
            ) : null}
          </div>

          <div className="grid gap-2 md:grid-cols-4">
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.decisionCard.gini")}
              </p>
              <p className="font-semibold">
                {card.distributional.giniBefore?.toFixed(4) ?? "-"}{" "}
                {t("pages.artifacts.decisionCard.to")}{" "}
                {card.distributional.giniAfter?.toFixed(4) ?? "-"}
              </p>
              <p className="text-muted text-xs">
                {t("pages.artifacts.decisionCard.delta")}{" "}
                {card.distributional.giniDelta?.toFixed(4) ?? "-"}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.decisionCard.winnersLosers")}
              </p>
              <p className="font-semibold">
                {card.distributional.winnersCount} /{" "}
                {card.distributional.losersCount}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.decisionCard.winnerShare")}
              </p>
              <p className="font-semibold">
                {(card.distributional.winnersShare * 100).toFixed(0)}%
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.decisionCard.vulnerableLosers")}
              </p>
              <p className="font-semibold">
                {card.distributional.vulnerableLosersCount}
              </p>
            </div>
          </div>

          {activeBreakdown ? (
            <div className="bg-canvas/20 border-line mt-3 h-64 rounded-lg border p-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={activeBreakdown.rows}
                  margin={{ top: 12, right: 16, left: 8, bottom: 8 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={chartTheme.grid}
                  />
                  <XAxis dataKey="cohortLabel" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="primaryDelta" name="Primary delta">
                    {activeBreakdown.rows.map((row) => (
                      <Cell
                        key={row.cohortLabel}
                        fill={
                          row.primaryDelta >= 0
                            ? row.isVulnerable
                              ? chartTheme.warning
                              : chartTheme.success
                            : chartTheme.alert
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
