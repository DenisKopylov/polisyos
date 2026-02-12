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

import StatusBadge from "../shared/StatusBadge";
import type { DecisionCardViewModel } from "../../lib/domain/decision";
import { parseDecisionCardPayload } from "../../lib/domain/decision";
import { formatDate, formatDuration } from "../../lib/utils";

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

export default function DecisionCardView({ payload, artifactKind }: DecisionCardViewProps) {
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
    return breakdowns.find((item) => item.dimensionLabel === selectedBreakdown) ?? breakdowns[0];
  }, [card?.distributional?.breakdowns, selectedBreakdown]);

  if (!card) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-canvas/30 p-4">
        <h3 className="mb-1 text-lg font-semibold">Decision Card</h3>
        <p className="text-sm text-muted">
          Unable to parse decision payload. Artifact kind: {artifactKind}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <section className="rounded-xl border border-line bg-panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs uppercase text-muted">Decision card ({card.sourceKind})</p>
            <h3 className="text-lg font-semibold">Run {card.runId}</h3>
            <p className="text-xs text-muted">Generated: {formatDate(card.generatedAt)}</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge label={card.verdict} kind={verdictKind(card.verdict)} />
            <StatusBadge label={`confidence:${card.confidence}`} kind={confidenceKind(card.confidence)} />
          </div>
        </div>

        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
            <p className="text-xs uppercase text-muted">Policy summary</p>
            <p className="font-semibold">{card.policySummary}</p>
            <p className="text-xs text-muted">interventions: {card.interventionCount}</p>
          </div>
          <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
            <p className="text-xs uppercase text-muted">Issues</p>
            <p className="font-semibold">
              blockers {card.issues.blockerCount} | warnings {card.issues.warningCount} | info {card.issues.infoCount}
            </p>
            {card.issues.blockedPasses.length > 0 ? (
              <p className="text-xs text-muted">blocked passes: {card.issues.blockedPasses.join(", ")}</p>
            ) : null}
          </div>
          <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
            <p className="text-xs uppercase text-muted">Duration</p>
            <p className="font-semibold">{formatDuration(card.totalDurationMs)}</p>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-line bg-panel p-4">
        <h4 className="mb-2 text-base font-semibold">Key metrics</h4>
        {card.keyMetrics.length > 0 ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {card.keyMetrics.map((metric) => (
              <article key={metric.name} className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
                <p className="text-xs uppercase text-muted">{metric.name}</p>
                <p className="font-semibold">
                  {metric.formatted}
                  {metric.unit ? ` ${metric.unit}` : ""}
                </p>
                {metric.ciLower !== null && metric.ciUpper !== null ? (
                  <p className="text-xs text-muted">
                    [{metric.ciLower.toFixed(2)}, {metric.ciUpper.toFixed(2)}]
                    {metric.ciLevel !== null ? ` @ ${(metric.ciLevel * 100).toFixed(0)}%` : ""}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">No key metrics in decision payload.</p>
        )}
      </section>

      {card.distributional ? (
        <section className="rounded-xl border border-line bg-panel p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-base font-semibold">Distributional impact</h4>
            {card.distributional.breakdowns.length > 1 ? (
              <select
                value={activeBreakdown?.dimensionLabel ?? ""}
                onChange={(event) => setSelectedBreakdown(event.target.value)}
                className="rounded-lg border border-line bg-panel px-2 py-1 text-sm"
              >
                {card.distributional.breakdowns.map((breakdown) => (
                  <option key={breakdown.dimensionLabel} value={breakdown.dimensionLabel}>
                    {breakdown.dimensionLabel}
                  </option>
                ))}
              </select>
            ) : null}
          </div>

          <div className="grid gap-2 md:grid-cols-4">
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
              <p className="text-xs uppercase text-muted">Gini</p>
              <p className="font-semibold">
                {card.distributional.giniBefore?.toFixed(4) ?? "-"} to {card.distributional.giniAfter?.toFixed(4) ?? "-"}
              </p>
              <p className="text-xs text-muted">delta {card.distributional.giniDelta?.toFixed(4) ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
              <p className="text-xs uppercase text-muted">Winners / Losers</p>
              <p className="font-semibold">
                {card.distributional.winnersCount} / {card.distributional.losersCount}
              </p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
              <p className="text-xs uppercase text-muted">Winner share</p>
              <p className="font-semibold">{(card.distributional.winnersShare * 100).toFixed(0)}%</p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
              <p className="text-xs uppercase text-muted">Vulnerable losers</p>
              <p className="font-semibold">{card.distributional.vulnerableLosersCount}</p>
            </div>
          </div>

          {activeBreakdown ? (
            <div className="mt-3 h-64 rounded-lg border border-line bg-canvas/20 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={activeBreakdown.rows} margin={{ top: 12, right: 16, left: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dbe3ed" />
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
                              ? "#7f9f2f"
                              : "#12805c"
                            : "#b5242f"
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
