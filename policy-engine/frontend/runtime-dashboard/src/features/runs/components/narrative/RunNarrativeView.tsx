import { useState } from "react";

import { cn } from "@/lib/utils";
import { Card } from "@/shared/ui/primitives";

import { NarrativeChapter } from "./shared/NarrativeChapter";
import { NarrativeTransition } from "./shared/NarrativeTransition";
import { InsightCallout } from "./shared/InsightCallout";

// ---------------------------------------------------------------------------
// Types — generic run narrative data (provided by parent)
// ---------------------------------------------------------------------------

export type NarrativeQuestion = {
  question: string;
  context?: string;
  policyDomain?: string;
};

export type NarrativeData = {
  sources: { label: string; status: "available" | "partial" | "missing" }[];
  coveragePct?: number;
};

export type NarrativeMethod = {
  methodology: string;
  rationale: string;
  alternatives?: string[];
};

export type NarrativeFindings = {
  estimate: number;
  ci?: { lower: number; upper: number; level: number };
  summary: string;
  chartSlot?: React.ReactNode;
};

export type NarrativeRobustness = {
  sensitivityGamma?: number;
  placeboPass?: boolean;
  boundsType?: string;
  summary: string;
};

export type NarrativeGovernance = {
  verdict: string;
  passCount: number;
  failCount: number;
  blockers?: string[];
};

export type NarrativeRecommendation = {
  headline: string;
  actions?: string[];
  caveats?: string[];
};

export type RunNarrativeData = {
  runId: string;
  question: NarrativeQuestion;
  data: NarrativeData;
  method: NarrativeMethod;
  findings: NarrativeFindings;
  robustness: NarrativeRobustness;
  governance: NarrativeGovernance;
  recommendation: NarrativeRecommendation;
};

// ---------------------------------------------------------------------------
// Chapter definitions
// ---------------------------------------------------------------------------

const CHAPTERS = [
  { id: "question", title: "The Question", subtitle: "What we set out to answer" },
  { id: "data", title: "Data Landscape", subtitle: "What evidence is available" },
  { id: "method", title: "Methodology", subtitle: "How we approached this" },
  { id: "findings", title: "Findings", subtitle: "What we discovered" },
  { id: "robustness", title: "Robustness", subtitle: "How confident are we" },
  { id: "governance", title: "Governance", subtitle: "Is this safe to act on" },
  { id: "recommendation", title: "Recommendation", subtitle: "What to do next" },
] as const;

type ChapterId = (typeof CHAPTERS)[number]["id"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type RunNarrativeViewProps = {
  narrative: RunNarrativeData;
  className?: string;
};

export function RunNarrativeView({
  narrative,
  className,
}: RunNarrativeViewProps) {
  const [activeChapter, setActiveChapter] = useState<ChapterId>("question");

  const statusColor = (s: string) =>
    s === "available"
      ? "var(--chart-success)"
      : s === "partial"
        ? "var(--chart-warning)"
        : "var(--chart-alert)";

  return (
    <div className={cn("flex gap-6", className)}>
      {/* Sidebar navigation */}
      <nav
        className="sticky top-20 hidden w-48 shrink-0 self-start lg:block"
        aria-label="Narrative chapters"
      >
        <ul className="space-y-1">
          {CHAPTERS.map((ch, i) => (
            <li key={ch.id}>
              <a
                href={`#${ch.id}`}
                onClick={() => setActiveChapter(ch.id)}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                  activeChapter === ch.id
                    ? "bg-[var(--chart-primary)]/10 font-semibold text-[var(--chart-primary)]"
                    : "text-muted hover:text-inherit",
                )}
              >
                <span className="text-xs font-bold">{i + 1}</span>
                <span className="truncate">{ch.title}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* Main narrative content */}
      <div className="min-w-0 flex-1 space-y-2">
        {/* 1. Question */}
        <NarrativeChapter id="question" number={1} title="The Question" subtitle="What we set out to answer">
          <Card className="space-y-3">
            <p className="text-lg font-semibold">{narrative.question.question}</p>
            {narrative.question.context && (
              <p className="text-muted text-sm">{narrative.question.context}</p>
            )}
            {narrative.question.policyDomain && (
              <span className="bg-surface border-line inline-block rounded-lg border px-2 py-1 text-xs font-medium">
                {narrative.question.policyDomain}
              </span>
            )}
          </Card>
        </NarrativeChapter>

        <NarrativeTransition label="Next: examining available data" />

        {/* 2. Data */}
        <NarrativeChapter id="data" number={2} title="Data Landscape" subtitle="What evidence is available">
          <Card className="space-y-3">
            {narrative.data.coveragePct != null && (
              <p className="text-sm">
                Overall evidence coverage:{" "}
                <span className="font-bold">
                  {Math.round(narrative.data.coveragePct * 100)}%
                </span>
              </p>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {narrative.data.sources.map((src) => (
                <div
                  key={src.label}
                  className="border-line flex items-center gap-2 rounded-xl border p-3"
                >
                  <span
                    className="size-2 rounded-full"
                    style={{ background: statusColor(src.status) }}
                  />
                  <span className="text-sm font-medium">{src.label}</span>
                  <span className="text-muted ms-auto text-xs capitalize">
                    {src.status}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </NarrativeChapter>

        <NarrativeTransition label="Next: selecting methodology" />

        {/* 3. Method */}
        <NarrativeChapter id="method" number={3} title="Methodology" subtitle="How we approached this">
          <Card className="space-y-3">
            <p className="text-sm">
              Selected:{" "}
              <span className="font-mono font-semibold">
                {narrative.method.methodology}
              </span>
            </p>
            <p className="text-muted text-sm">{narrative.method.rationale}</p>
            {narrative.method.alternatives &&
              narrative.method.alternatives.length > 0 && (
                <InsightCallout level="info" title="Alternatives considered">
                  {narrative.method.alternatives.join(", ")}
                </InsightCallout>
              )}
          </Card>
        </NarrativeChapter>

        <NarrativeTransition label="Next: presenting findings" />

        {/* 4. Findings */}
        <NarrativeChapter id="findings" number={4} title="Findings" subtitle="What we discovered">
          <Card className="space-y-3">
            <div className="flex items-baseline gap-4">
              <span className="font-mono text-3xl font-bold">
                {narrative.findings.estimate >= 0 ? "+" : ""}
                {narrative.findings.estimate.toFixed(4)}
              </span>
              {narrative.findings.ci && (
                <span className="text-muted text-sm">
                  {narrative.findings.ci.level}% CI: [
                  {narrative.findings.ci.lower.toFixed(4)},{" "}
                  {narrative.findings.ci.upper.toFixed(4)}]
                </span>
              )}
            </div>
            <p className="text-sm">{narrative.findings.summary}</p>
            {narrative.findings.chartSlot}
          </Card>
        </NarrativeChapter>

        <NarrativeTransition label="Next: checking robustness" />

        {/* 5. Robustness */}
        <NarrativeChapter id="robustness" number={5} title="Robustness" subtitle="How confident are we">
          <Card className="space-y-3">
            <p className="text-sm">{narrative.robustness.summary}</p>
            <div className="flex flex-wrap gap-4 text-sm">
              {narrative.robustness.sensitivityGamma != null && (
                <div>
                  <span className="text-muted text-xs">Sensitivity</span>
                  <p className="font-mono font-semibold">
                    {"\u0393"} = {narrative.robustness.sensitivityGamma.toFixed(1)}
                  </p>
                </div>
              )}
              {narrative.robustness.placeboPass != null && (
                <div>
                  <span className="text-muted text-xs">Placebo test</span>
                  <p
                    className="font-semibold"
                    style={{
                      color: narrative.robustness.placeboPass
                        ? "var(--chart-success)"
                        : "var(--chart-alert)",
                    }}
                  >
                    {narrative.robustness.placeboPass ? "Pass" : "Fail"}
                  </p>
                </div>
              )}
              {narrative.robustness.boundsType && (
                <div>
                  <span className="text-muted text-xs">Bounds</span>
                  <p className="font-semibold">{narrative.robustness.boundsType}</p>
                </div>
              )}
            </div>
          </Card>
        </NarrativeChapter>

        <NarrativeTransition label="Next: governance review" />

        {/* 6. Governance */}
        <NarrativeChapter id="governance" number={6} title="Governance" subtitle="Is this safe to act on">
          <Card className="space-y-3">
            <div className="flex items-center gap-4">
              <span
                className="rounded-xl px-3 py-1 text-sm font-bold"
                style={{
                  background:
                    narrative.governance.failCount === 0
                      ? "color-mix(in srgb, var(--chart-success) 12%, transparent)"
                      : "color-mix(in srgb, var(--chart-alert) 12%, transparent)",
                  color:
                    narrative.governance.failCount === 0
                      ? "var(--chart-success)"
                      : "var(--chart-alert)",
                }}
              >
                {narrative.governance.verdict}
              </span>
              <span className="text-sm">
                <span className="font-semibold text-[var(--chart-success)]">
                  {narrative.governance.passCount}
                </span>{" "}
                passed,{" "}
                <span className="font-semibold text-[var(--chart-alert)]">
                  {narrative.governance.failCount}
                </span>{" "}
                failed
              </span>
            </div>
            {narrative.governance.blockers &&
              narrative.governance.blockers.length > 0 && (
                <InsightCallout level="critical" title="Blockers">
                  <ul className="space-y-1">
                    {narrative.governance.blockers.map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                </InsightCallout>
              )}
          </Card>
        </NarrativeChapter>

        <NarrativeTransition label="Final: recommendation" />

        {/* 7. Recommendation */}
        <NarrativeChapter id="recommendation" number={7} title="Recommendation" subtitle="What to do next">
          <Card className="space-y-3">
            <p className="text-lg font-semibold">
              {narrative.recommendation.headline}
            </p>
            {narrative.recommendation.actions &&
              narrative.recommendation.actions.length > 0 && (
                <div>
                  <p className="text-muted mb-1 text-xs font-semibold uppercase">
                    Recommended actions
                  </p>
                  <ul className="space-y-1 text-sm">
                    {narrative.recommendation.actions.map((a) => (
                      <li key={a} className="flex items-start gap-2">
                        <span className="text-[var(--chart-success)]">{"\u2713"}</span>
                        <span>{a}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            {narrative.recommendation.caveats &&
              narrative.recommendation.caveats.length > 0 && (
                <InsightCallout level="warning" title="Caveats">
                  <ul className="space-y-1">
                    {narrative.recommendation.caveats.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </InsightCallout>
              )}
          </Card>
        </NarrativeChapter>
      </div>
    </div>
  );
}
