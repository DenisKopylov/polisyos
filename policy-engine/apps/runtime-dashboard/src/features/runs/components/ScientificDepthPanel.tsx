import { useMemo, useState } from "react";

import {
  buildScientificDepthSnapshot,
  type IdentifiabilityCell,
  type IdentifiabilityState,
  type IdentificationRemedy,
  type SensitivityClaim,
  type StressSceneStatus,
} from "@/features/runs/domain/scientificDepth";
import type { RunInspectorSummary } from "@/features/runs/context/RunInspectorContext";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  cn,
  formatDate,
  formatNumber,
  formatPercent,
} from "@/shared/lib/utils";
import { Badge, Button, Slider } from "@polisyos/atlas-ui";

function identifiabilityKind(state: IdentifiabilityState) {
  if (state === "identified") return "ok";
  if (state === "estimated") return "warn";
  if (state === "assumed") return "warn";
  if (state === "unknown") return "neutral";
  return assertNeverIdentifiability(state);
}

function assertNeverIdentifiability(value: never): never {
  throw new TypeError(`Unhandled generated identifiability member: ${value}`);
}

function identifiabilityLabel(state: IdentifiabilityState) {
  return state.replaceAll("_", " ");
}

function stressKind(status: StressSceneStatus) {
  if (status === "pass") return "ok";
  if (status === "warn") return "warn";
  return "fail";
}

function formatBound(value: number | null, unavailable: string) {
  return typeof value === "number"
    ? formatNumber(value, { maximumFractionDigits: 2 })
    : unavailable;
}

function RemedyLine({ remedy }: { remedy: IdentificationRemedy }) {
  const { t } = useI18n();

  return (
    <li>
      {t("phase33.identifiability.wizardOption", {
        effort: t(`phase33.identifiability.effort.${remedy.effort}`),
        kind: t(`phase33.identifiability.remedyKind.${remedy.kind}`),
        ref: remedy.ref,
      })}
    </li>
  );
}

function IdentifiabilityDetail({ cell }: { cell: IdentifiabilityCell }) {
  const { t } = useI18n();

  return (
    <div className="border-line bg-background/55 rounded-2xl border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <strong>{cell.label}</strong>
        <Badge kind={identifiabilityKind(cell.state)}>
          {identifiabilityLabel(cell.state)}
        </Badge>
      </div>
      <div className="mt-3 grid gap-2 text-sm md:grid-cols-3">
        <div>
          <p className="text-muted text-xs uppercase">
            {t("phase33.identifiability.bounds")}
          </p>
          <p className="font-mono">
            {t("phase33.identifiability.interval", {
              lower: formatBound(cell.bounds.lower, t("common.unavailable")),
              method: cell.bounds.method ?? t("common.unavailable"),
              upper: formatBound(cell.bounds.upper, t("common.unavailable")),
            })}
          </p>
        </div>
        <div>
          <p className="text-muted text-xs uppercase">
            {t("phase33.identifiability.remedy")}
          </p>
          <p>
            {t("phase33.identifiability.remedyMeta", {
              effort: t(`phase33.identifiability.effort.${cell.remedy.effort}`),
              kind: t(`phase33.identifiability.remedyKind.${cell.remedy.kind}`),
              ref: cell.remedy.ref,
            })}
          </p>
        </div>
        <div>
          <p className="text-muted text-xs uppercase">
            {t("phase33.identifiability.impact")}
          </p>
          <p>
            {t("phase33.identifiability.impactMeta", {
              policies:
                cell.decisionImpact.policyRecommendations === null
                  ? t("common.unavailable")
                  : formatNumber(cell.decisionImpact.policyRecommendations),
              quantities: formatNumber(cell.decisionImpact.quantities),
            })}
          </p>
        </div>
      </div>
      <div className="border-line mt-3 border-t pt-3">
        <p className="text-muted text-xs uppercase">
          {t("phase33.identifiability.wizardTitle")}
        </p>
        <ul className="mt-2 space-y-1 text-sm">
          {cell.remedies.map((remedy) => (
            <RemedyLine
              key={`${remedy.kind}-${remedy.effort}-${remedy.ref}`}
              remedy={remedy}
            />
          ))}
        </ul>
      </div>
    </div>
  );
}

function SensitivityClaimRow({ claim }: { claim: SensitivityClaim }) {
  const { t } = useI18n();

  return (
    <div
      className={cn(
        "border-line grid gap-2 rounded-xl border px-3 py-2 text-sm md:grid-cols-[minmax(0,1fr)_auto]",
        claim.extinguished ? "bg-danger/10" : "bg-surface/70",
      )}
    >
      <div>
        <p className="font-semibold">{claim.label}</p>
        <p className="text-muted mt-1 text-xs">
          {t(`phase33.sensitivity.explanation.${claim.explanationKey}`, {
            eValue: formatNumber(claim.eValue, { maximumFractionDigits: 2 }),
            threshold: formatNumber(claim.threshold, {
              maximumFractionDigits: 2,
            }),
          })}
        </p>
      </div>
      <Badge kind={claim.extinguished ? "fail" : "ok"}>
        {t("phase33.sensitivity.eValue", {
          value: formatNumber(claim.eValue, { maximumFractionDigits: 2 }),
        })}
      </Badge>
    </div>
  );
}

export function ScientificDepthPanel({
  runId,
  summary,
}: {
  runId: string;
  summary: RunInspectorSummary;
}) {
  const { t } = useI18n();
  const [threshold, setThreshold] = useState(1.5);
  const [cohortIndex, setCohortIndex] = useState(1);
  const snapshot = useMemo(
    () =>
      buildScientificDepthSnapshot({
        activeCohortIndex: cohortIndex,
        decisionView: summary.decisionView,
        evidenceContext: summary.evidenceContext,
        governanceIssues: summary.governanceIssues,
        runId,
        sensitivityThreshold: threshold,
      }),
    [
      cohortIndex,
      runId,
      summary.decisionView,
      summary.evidenceContext,
      summary.governanceIssues,
      threshold,
    ],
  );
  const [selectedCellId, setSelectedCellId] = useState<string | null>(
    snapshot.identifiability.initialCellId,
  );
  const selectedCell =
    snapshot.identifiability.cells.find(
      (cell) =>
        cell.id === (selectedCellId ?? snapshot.identifiability.initialCellId),
    ) ??
    snapshot.identifiability.cells[0] ??
    null;
  const activeCohortTime =
    snapshot.cohort.timeline.find(
      (point) => point.index === snapshot.cohort.activeIndex,
    ) ?? snapshot.cohort.timeline[0];

  return (
    <section className="space-y-4" data-testid="scientific-depth-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("phase33.eyebrow")}</p>
          <h3>{t("phase33.title")}</h3>
        </div>
        <Badge kind="neutral">{t("phase33.packetIntegrated")}</Badge>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="identifiability-surface-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase33.identifiability.eyebrow")}</p>
              <h4>{t("phase33.identifiability.title")}</h4>
            </div>
          </div>
          <div
            className="mt-4 grid gap-2 md:grid-cols-4"
            data-testid="identifiability-summary"
          >
            {snapshot.identifiability.summary.map(({ count, state }) => (
              <div key={state} className="compact-metric">
                <span>{identifiabilityLabel(state)}</span>
                <strong>{formatNumber(count)}</strong>
              </div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
            {snapshot.identifiability.cells.map((cell) => (
              <Button
                key={cell.id}
                type="button"
                variant="ghost"
                onClick={() => setSelectedCellId(cell.id)}
                className={cn(
                  "border-line bg-background/55 h-auto justify-start rounded-xl border px-3 py-3 text-left",
                  cell.id === selectedCell?.id &&
                    "border-accent/50 bg-accent/10",
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold">
                    {cell.label}
                  </span>
                  <span className="text-muted mt-1 block text-xs">
                    {identifiabilityLabel(cell.state)}
                  </span>
                </span>
              </Button>
            ))}
          </div>
          <div className="mt-3">
            {selectedCell ? (
              <IdentifiabilityDetail cell={selectedCell} />
            ) : (
              <p className="text-muted text-sm">
                {t("phase33.identifiability.empty")}
              </p>
            )}
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="sensitivity-rotor-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase33.sensitivity.eyebrow")}</p>
              <h4>{t("phase33.sensitivity.title")}</h4>
            </div>
            <Badge kind={snapshot.sensitivity.verdictChanged ? "fail" : "ok"}>
              {snapshot.sensitivity.verdictChanged
                ? t("phase33.sensitivity.verdictChanged")
                : t("phase33.sensitivity.verdictStable")}
            </Badge>
          </div>
          <div className="mt-4 space-y-3">
            <div>
              <div className="mb-2 flex items-center justify-between gap-3 text-sm">
                <span className="font-semibold">
                  {t("phase33.sensitivity.threshold")}
                </span>
                <span className="font-mono">
                  {formatNumber(threshold, { maximumFractionDigits: 2 })}
                </span>
              </div>
              <Slider
                aria-label={t("phase33.sensitivity.threshold")}
                max={3}
                min={1}
                step={0.05}
                value={[threshold]}
                onValueChange={([value]) => setThreshold(value ?? threshold)}
              />
            </div>
            <div className="grid gap-2 md:grid-cols-4">
              <div className="compact-metric">
                <span>{t("phase33.sensitivity.remaining")}</span>
                <strong>
                  {formatNumber(snapshot.sensitivity.remainingClaims)}
                </strong>
              </div>
              <div className="compact-metric">
                <span>{t("phase33.sensitivity.extinguished")}</span>
                <strong>
                  {formatNumber(snapshot.sensitivity.extinguishedClaims)}
                </strong>
              </div>
              <div
                className="compact-metric"
                data-testid="sensitivity-decision-bearing-share"
              >
                <span>{t("phase33.sensitivity.decisionBearingGone")}</span>
                <strong>
                  {formatPercent(
                    snapshot.sensitivity.decisionBearingExtinguishedShare,
                    { maximumFractionDigits: 0 },
                  )}
                </strong>
              </div>
              <div className="compact-metric">
                <span>{t("phase33.sensitivity.fairness")}</span>
                <strong>
                  {snapshot.sensitivity.fairnessGateChanged
                    ? t("common.yes")
                    : t("common.no")}
                </strong>
              </div>
            </div>
            <div className="grid max-h-72 gap-2 overflow-auto pr-1">
              {snapshot.sensitivity.claims.map((claim) => (
                <SensitivityClaimRow key={claim.id} claim={claim} />
              ))}
              {snapshot.sensitivity.claims.length === 0 ? (
                <p className="text-muted text-sm">
                  {t("phase33.sensitivity.empty")}
                </p>
              ) : null}
            </div>
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="cohort-time-traveler-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase33.cohort.eyebrow")}</p>
              <h4>{t("phase33.cohort.title")}</h4>
            </div>
            <Badge kind="neutral">
              {activeCohortTime?.validAt
                ? formatDate(activeCohortTime.validAt)
                : t("common.unavailable")}
            </Badge>
          </div>
          <div className="mt-4 space-y-3">
            <Slider
              aria-label={t("phase33.cohort.validTime")}
              max={snapshot.cohort.timeline.length - 1}
              min={0}
              step={1}
              value={[snapshot.cohort.activeIndex]}
              onValueChange={([value]) => setCohortIndex(value ?? cohortIndex)}
            />
            <div className="grid gap-2 md:grid-cols-3">
              {snapshot.cohort.timeline.map((point) => (
                <div
                  key={point.index}
                  className={cn(
                    "border-line rounded-xl border px-3 py-2 text-sm",
                    point.index === snapshot.cohort.activeIndex
                      ? "bg-accent/10 border-accent/40"
                      : "bg-background/55",
                  )}
                >
                  <strong>{t(`phase33.cohort.timeline.${point.label}`)}</strong>
                  <p className="text-muted mt-1 text-xs">
                    {point.validAt
                      ? formatDate(point.validAt)
                      : t("common.unavailable")}
                  </p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {snapshot.cohort.filters.map((filter) => (
                <Badge key={filter.id} kind="outline">
                  {t("phase33.cohort.filter", {
                    label: t(`phase33.cohort.filterLabel.${filter.label}`),
                    value: filter.value,
                  })}
                </Badge>
              ))}
              <Badge kind="neutral">
                {t("phase33.cohort.policyOverlay", {
                  ref: snapshot.cohort.policyOverlay.ref,
                  verdict: snapshot.cohort.policyOverlay.verdict,
                })}
              </Badge>
            </div>
            <div className="space-y-2">
              {snapshot.cohort.transitions.map((transition) => (
                <div
                  key={transition.cohortId}
                  className="border-line bg-background/55 rounded-xl border p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <strong>{transition.cohortLabel}</strong>
                    <Badge
                      kind={
                        transition.policyEffect === "pass"
                          ? "ok"
                          : transition.policyEffect === "fail"
                            ? "fail"
                            : "warn"
                      }
                    >
                      {t(`phase33.cohort.effect.${transition.policyEffect}`)}
                    </Badge>
                  </div>
                  <div className="mt-3 grid gap-2">
                    {[
                      ["baseline", transition.baselineShare],
                      ["observed", transition.observedShare],
                      ["overlay", transition.overlayShare],
                    ].map(([kind, share]) => (
                      <div
                        key={kind}
                        className="grid grid-cols-[5.5rem_minmax(0,1fr)_3rem] items-center gap-2 text-xs"
                      >
                        <span className="text-muted">
                          {t(`phase33.cohort.share.${kind}`)}
                        </span>
                        <div className="bg-muted/25 h-2 overflow-hidden rounded-full">
                          <div
                            className={cn(
                              "h-full rounded-full",
                              kind === "overlay" ? "bg-warning" : "bg-accent",
                            )}
                            style={{
                              width: `${Math.max(
                                4,
                                Math.min(100, Number(share) * 100),
                              )}%`,
                            }}
                          />
                        </div>
                        <span className="font-mono">
                          {formatPercent(Number(share), {
                            maximumFractionDigits: 0,
                          })}
                        </span>
                      </div>
                    ))}
                    <span className="text-muted text-xs">
                      {t("phase33.cohort.flow", {
                        from: t(`phase33.cohort.state.${transition.fromState}`),
                        share: formatPercent(transition.observedShare, {
                          maximumFractionDigits: 0,
                        }),
                        to: t(`phase33.cohort.state.${transition.toState}`),
                      })}
                    </span>
                  </div>
                </div>
              ))}
              {snapshot.cohort.transitions.length === 0 ? (
                <p className="text-muted text-sm">
                  {t("phase33.cohort.empty")}
                </p>
              ) : null}
            </div>
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="stress-test-theatre-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase33.stress.eyebrow")}</p>
              <h4>{t("phase33.stress.title")}</h4>
            </div>
            <Badge
              kind={
                snapshot.stress.summary.blocked > 0
                  ? "fail"
                  : snapshot.stress.summary.warned > 0
                    ? "warn"
                    : "ok"
              }
            >
              {t("phase33.stress.summary", {
                blocked: formatNumber(snapshot.stress.summary.blocked),
                warned: formatNumber(snapshot.stress.summary.warned),
              })}
            </Badge>
          </div>
          <div className="mt-4 space-y-2">
            {snapshot.stress.citedSceneRef ? (
              <div className="border-warning/40 bg-warning/10 rounded-xl border p-3">
                <p className="text-sm font-semibold">
                  {t("phase33.stress.citedScene", {
                    ref: snapshot.stress.citedSceneRef,
                  })}
                </p>
              </div>
            ) : null}
            {snapshot.stress.scenes.map((scene) => (
              <div
                key={scene.id}
                className={cn(
                  "border-line bg-background/55 grid gap-2 rounded-xl border p-3 text-sm md:grid-cols-[minmax(0,1fr)_auto]",
                  scene.actual === "block" && "border-danger/40 bg-danger/10",
                )}
              >
                <div>
                  <p className="font-semibold">
                    {t("phase33.stress.act", {
                      act: formatNumber(scene.act),
                      title: t(scene.labelKey),
                    })}
                  </p>
                  <p className="text-muted mt-1 text-xs">
                    {t("phase33.stress.ref", {
                      ref: scene.immutableRef,
                    })}
                  </p>
                  <p className="text-muted mt-2 text-xs">
                    {t("phase33.stress.diff", {
                      diff: t(`phase33.stress.diffState.${scene.diff}`),
                      reaction: t(scene.reactionKey),
                    })}
                  </p>
                  {scene.issueRefs.length > 0 ? (
                    <p className="text-muted mt-1 text-xs">
                      {t("phase33.stress.issueRefs", {
                        refs: scene.issueRefs.join(", "),
                      })}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2 md:justify-end">
                  <Badge kind={stressKind(scene.expected)}>
                    {t("phase33.stress.expected", {
                      status: t(`phase33.stress.status.${scene.expected}`),
                    })}
                  </Badge>
                  <Badge kind={stressKind(scene.actual)}>
                    {t("phase33.stress.actual", {
                      status: t(`phase33.stress.status.${scene.actual}`),
                    })}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
