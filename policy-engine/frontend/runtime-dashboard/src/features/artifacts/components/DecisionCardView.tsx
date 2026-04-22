import { useMemo, useState } from "react";
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
import type { BadgeKind } from "@/shared/ui";
import { DecisionCard, ProvenanceStrip, Select, chartTheme } from "@/shared/ui";
import { EvidenceSigil } from "@/shared/brand/EvidenceSigil";
import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";
import type { DecisionCardViewModel } from "@/lib/domain/decision";
import { parseDecisionCardPayload } from "@/lib/domain/decision";
import { formatDate, formatDuration } from "@/lib/utils";

type DecisionCardViewProps = {
  payload: unknown;
  artifactKind: string;
};

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

function decisionEyebrowItems(card: DecisionCardViewModel): ProvenanceItem[] {
  const items: ProvenanceItem[] = [
    {
      id: "intervention",
      glyph: "intervention",
      label: `${card.interventionCount} interventions`,
    },
  ];
  if (card.issues.blockerCount > 0) {
    items.push({
      id: "governance",
      glyph: "blocker",
      label: "Blocked",
      intent: "blocked",
    });
  } else {
    items.push({
      id: "governance",
      glyph: "governance-pass",
      label: "Governance pass",
      intent: "verified",
    });
  }
  items.push({
    id: "evidence",
    glyph: "evidence",
    label: card.confidence === "HIGH" ? "Strong evidence" : "Weak evidence",
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

export default function DecisionCardView({
  payload,
  artifactKind,
}: DecisionCardViewProps) {
  const card = useMemo(() => parseDecisionCardPayload(payload), [payload]);
  const [selectedBreakdown, setSelectedBreakdown] = useState<string>(
    card?.distributional?.breakdowns[0]?.dimensionLabel ?? "",
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
        <h3 className="mb-1 text-lg font-semibold">Decision Card</h3>
        <p className="text-muted text-sm">
          Unable to parse decision payload. Artifact kind: {artifactKind}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <DecisionCard
        title={`Run ${card.runId}`}
        subtitle={
          <>
            <span>Decision card ({card.sourceKind})</span>
            <span className="text-muted mx-2">·</span>
            <span>Generated: {formatDate(card.generatedAt)}</span>
          </>
        }
        eyebrow={
          <ProvenanceStrip
            title="Decision packet"
            items={decisionEyebrowItems(card)}
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
            label: "Interventions",
            value: card.interventionCount,
          },
          {
            label: "Issues",
            value: `blockers ${card.issues.blockerCount} | warnings ${card.issues.warningCount} | info ${card.issues.infoCount}`,
          },
          {
            label: "Blocked passes",
            value:
              card.issues.blockedPasses.length > 0
                ? card.issues.blockedPasses.join(", ")
                : "-",
          },
          {
            label: "Duration",
            value: formatDuration(card.totalDurationMs),
          },
        ]}
      />

      <section className="border-line bg-panel rounded-xl border p-4">
        <h4 className="mb-2 text-base font-semibold">Key metrics</h4>
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
                {metric.testLabel || metric.pValue !== null || metric.pAdj !== null ? (
                  <p className="text-muted text-xs">
                    {metric.testLabel ?? "Stat test"}
                    {metric.pAdj !== null
                      ? `, p_adj=${metric.pAdj.toFixed(4)}`
                      : metric.pValue !== null
                        ? `, p=${metric.pValue.toFixed(4)}`
                        : ""}
                    {metric.significant !== null
                      ? metric.significant
                        ? ", significant"
                        : ", not significant"
                      : ""}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="text-muted text-sm">
            No key metrics in decision payload.
          </p>
        )}
      </section>

      <MetricValidationComparisonTable
        title="Metric validation"
        comparisons={card.metricComparisons}
        familyAdjustment={card.metricValidationFamilyAdjustment}
      />

      {card.distributional ? (
        <section className="border-line bg-panel rounded-xl border p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-base font-semibold">Distributional impact</h4>
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
              <p className="text-muted text-xs uppercase">Gini</p>
              <p className="font-semibold">
                {card.distributional.giniBefore?.toFixed(4) ?? "-"} to{" "}
                {card.distributional.giniAfter?.toFixed(4) ?? "-"}
              </p>
              <p className="text-muted text-xs">
                delta {card.distributional.giniDelta?.toFixed(4) ?? "-"}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
              <p className="text-muted text-xs uppercase">Winners / Losers</p>
              <p className="font-semibold">
                {card.distributional.winnersCount} /{" "}
                {card.distributional.losersCount}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
              <p className="text-muted text-xs uppercase">Winner share</p>
              <p className="font-semibold">
                {(card.distributional.winnersShare * 100).toFixed(0)}%
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
              <p className="text-muted text-xs uppercase">Vulnerable losers</p>
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
