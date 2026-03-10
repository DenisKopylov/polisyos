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

import type { BadgeKind } from "@/shared/ui";
import { Badge, DecisionCard, Select, chartTheme } from "@/shared/ui";
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
      <div className="bg-canvas/30 rounded-xl border border-dashed border-line p-4">
        <h3 className="mb-1 text-lg font-semibold">Decision Card</h3>
        <p className="text-sm text-muted">
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
            <span className="mx-2 text-muted">·</span>
            <span>Generated: {formatDate(card.generatedAt)}</span>
          </>
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

      <section className="rounded-xl border border-line bg-panel p-4">
        <h4 className="mb-2 text-base font-semibold">Key metrics</h4>
        {card.keyMetrics.length > 0 ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {card.keyMetrics.map((metric) => (
              <article
                key={metric.name}
                className="bg-canvas/30 rounded-lg border border-line p-2 text-sm"
              >
                <p className="text-xs uppercase text-muted">{metric.name}</p>
                <p className="font-semibold">
                  {metric.formatted}
                  {metric.unit ? ` ${metric.unit}` : ""}
                </p>
                {metric.ciLower !== null && metric.ciUpper !== null ? (
                  <p className="text-xs text-muted">
                    [{metric.ciLower.toFixed(2)}, {metric.ciUpper.toFixed(2)}]
                    {metric.ciLevel !== null
                      ? ` @ ${(metric.ciLevel * 100).toFixed(0)}%`
                      : ""}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">
            No key metrics in decision payload.
          </p>
        )}
      </section>

      {card.distributional ? (
        <section className="rounded-xl border border-line bg-panel p-4">
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
            <div className="bg-canvas/30 rounded-lg border border-line p-2 text-sm">
              <p className="text-xs uppercase text-muted">Gini</p>
              <p className="font-semibold">
                {card.distributional.giniBefore?.toFixed(4) ?? "-"} to{" "}
                {card.distributional.giniAfter?.toFixed(4) ?? "-"}
              </p>
              <p className="text-xs text-muted">
                delta {card.distributional.giniDelta?.toFixed(4) ?? "-"}
              </p>
            </div>
            <div className="bg-canvas/30 rounded-lg border border-line p-2 text-sm">
              <p className="text-xs uppercase text-muted">Winners / Losers</p>
              <p className="font-semibold">
                {card.distributional.winnersCount} /{" "}
                {card.distributional.losersCount}
              </p>
            </div>
            <div className="bg-canvas/30 rounded-lg border border-line p-2 text-sm">
              <p className="text-xs uppercase text-muted">Winner share</p>
              <p className="font-semibold">
                {(card.distributional.winnersShare * 100).toFixed(0)}%
              </p>
            </div>
            <div className="bg-canvas/30 rounded-lg border border-line p-2 text-sm">
              <p className="text-xs uppercase text-muted">Vulnerable losers</p>
              <p className="font-semibold">
                {card.distributional.vulnerableLosersCount}
              </p>
            </div>
          </div>

          {activeBreakdown ? (
            <div className="bg-canvas/20 mt-3 h-64 rounded-lg border border-line p-2">
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
