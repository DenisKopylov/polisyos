import { useEffect, useMemo, useState } from "react";

import type { RunInspectorSummary } from "@/features/runs/context/RunInspectorContext";
import {
  buildDisputeRecords,
  DISPUTES_CHANGED_EVENT,
  readStoredDisputes,
} from "@/features/runs/domain/disputes";
import {
  acknowledgeReviewSection,
  buildPublicSectorReadinessSnapshot,
  markReviewSectionOpened,
  PUBLIC_READINESS_CHANGED_EVENT,
  readStoredReviewAttention,
  type ReadinessSectionId,
  type StakeholderLens,
  STAKEHOLDER_LENSES,
  writeStoredReviewAttention,
} from "@/features/runs/domain/publicSectorReadiness";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn, formatDate, formatNumber } from "@/shared/lib/utils";
import { Quantity } from "@/shared/ui/quantity";
import { Badge, Button } from "@polisyos/atlas-ui";

const DIAGNOSTIC_CENSUS_LABEL = "Diagnostic census";
const DIAGNOSTIC_FINDINGS_LABEL = "Diagnostic findings";
const RECORDED_FINDING_LABEL = "recorded finding";
const NO_DIAGNOSTIC_FINDINGS_LABEL = "No diagnostic findings recorded.";

function displayOwnerLabel(value: string | null, unavailable: string) {
  return value?.replaceAll("_", " ") ?? unavailable;
}

function LensButton({
  active,
  lens,
  onSelect,
}: {
  active: boolean;
  lens: StakeholderLens;
  onSelect: (lens: StakeholderLens) => void;
}) {
  const { t } = useI18n();

  return (
    <Button
      type="button"
      variant="ghost"
      className={cn(
        "border-line rounded-full border px-3 py-1.5 text-xs",
        active && "border-accent/50 bg-accent/10 text-accent",
      )}
      onClick={() => onSelect(lens)}
    >
      {t(`phase34.lens.${lens}`)}
    </Button>
  );
}

export function PublicSectorReadinessPanel({
  runId,
  summary,
}: {
  runId: string;
  summary: RunInspectorSummary;
}) {
  const { t } = useI18n();
  const [lens, setLens] = useState<StakeholderLens>("operator");
  const [now, setNow] = useState(() => new Date().toISOString());
  const [reviewState, setReviewState] = useState(() =>
    readStoredReviewAttention(runId),
  );
  const [localDisputes, setLocalDisputes] = useState(() =>
    readStoredDisputes(runId),
  );

  useEffect(() => {
    setReviewState(readStoredReviewAttention(runId));
    setLocalDisputes(readStoredDisputes(runId));
  }, [runId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(new Date().toISOString());
    }, 1_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const onDisputesChanged = (event: Event) => {
      const detail = (event as CustomEvent<{ runId?: string }>).detail;
      if (!detail?.runId || detail.runId === runId) {
        setLocalDisputes(readStoredDisputes(runId));
      }
    };
    const onReadinessChanged = (event: Event) => {
      const detail = (event as CustomEvent<{ runId?: string }>).detail;
      if (!detail?.runId || detail.runId === runId) {
        setReviewState(readStoredReviewAttention(runId));
      }
    };
    window.addEventListener(DISPUTES_CHANGED_EVENT, onDisputesChanged);
    window.addEventListener(PUBLIC_READINESS_CHANGED_EVENT, onReadinessChanged);
    return () => {
      window.removeEventListener(DISPUTES_CHANGED_EVENT, onDisputesChanged);
      window.removeEventListener(
        PUBLIC_READINESS_CHANGED_EVENT,
        onReadinessChanged,
      );
    };
  }, [runId]);

  const disputes = useMemo(
    () => buildDisputeRecords(summary.governanceIssues, localDisputes),
    [localDisputes, summary.governanceIssues],
  );
  const snapshot = useMemo(
    () =>
      buildPublicSectorReadinessSnapshot({
        decisionValidityStatus: summary.run?.decision_validity_status,
        decisionView: summary.decisionView,
        disputes,
        evidenceContext: summary.evidenceContext,
        governanceIssues: summary.governanceIssues,
        lens,
        now,
        reviewState,
        runId,
      }),
    [
      disputes,
      lens,
      now,
      reviewState,
      runId,
      summary.decisionView,
      summary.evidenceContext,
      summary.governanceIssues,
      summary.run?.decision_validity_status,
    ],
  );

  const updateReviewState = (next: typeof reviewState) => {
    setReviewState(next);
    writeStoredReviewAttention(runId, next);
  };
  const markOpened = (sectionId: ReadinessSectionId) => {
    updateReviewState(
      markReviewSectionOpened({
        at: new Date().toISOString(),
        runId,
        sectionId,
        state: reviewState,
      }),
    );
  };
  const acknowledge = (sectionId: ReadinessSectionId) => {
    updateReviewState(
      acknowledgeReviewSection({
        at: new Date().toISOString(),
        runId,
        sectionId,
        state: reviewState,
      }),
    );
  };

  return (
    <section className="space-y-4" data-testid="public-sector-readiness-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("phase34.eyebrow")}</p>
          <h3>{t("phase34.title")}</h3>
          <p className="topbar-subtitle mt-2">{t("phase34.body")}</p>
        </div>
        <Badge kind="neutral">{formatNumber(snapshot.findings.length)}</Badge>
      </div>

      {snapshot.fairness.sentinel ? (
        <div
          className="border-line bg-surface/80 rounded-2xl border p-3"
          data-testid="fairness-sentinel-banner"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{t("phase34.fairness.sentinel")}</p>
              <p className="text-muted mt-1 text-sm">
                {t("phase34.fairness.sentinelBody", {
                  group: snapshot.fairness.sentinel.groupLabel,
                  ratio: formatNumber(snapshot.fairness.sentinel.ratio, {
                    maximumFractionDigits: 2,
                  }),
                  threshold: formatNumber(
                    snapshot.fairness.sentinel.threshold,
                    {
                      maximumFractionDigits: 2,
                    },
                  ),
                })}
              </p>
            </div>
            <Badge kind="neutral">{snapshot.fairness.sentinel.auditRef}</Badge>
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="stakeholder-lens-switcher"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase34.lens.eyebrow")}</p>
              <h4>{t("phase34.lens.title")}</h4>
            </div>
            <Badge kind="neutral">{snapshot.decisionHash}</Badge>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {STAKEHOLDER_LENSES.map((item) => (
              <LensButton
                key={item}
                active={item === lens}
                lens={item}
                onSelect={setLens}
              />
            ))}
          </div>
          <div className="mt-4 grid gap-2 text-sm">
            <p>
              <strong>{t("phase34.lens.emphasis")}: </strong>
              {snapshot.lens.emphasis.join(", ")}
            </p>
            <p>
              <strong>{t("phase34.lens.riskOrder")}: </strong>
              {snapshot.lens.riskOrder
                .map((kind) => t(`phase34.blockKind.${kind}`))
                .join(" / ")}
            </p>
            <p>
              <strong>{t("phase34.lens.collapsed")}: </strong>
              {snapshot.lens.collapsedSections.join(", ")}
            </p>
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="approval-blockers-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{DIAGNOSTIC_CENSUS_LABEL}</p>
              <h4>{DIAGNOSTIC_FINDINGS_LABEL}</h4>
            </div>
            <Badge kind="neutral">
              {formatNumber(snapshot.findings.length)}
            </Badge>
          </div>
          <div className="mt-4 space-y-2">
            {snapshot.findings.map((item) => (
              <article
                key={item.id}
                className="border-line bg-background/55 rounded-xl border p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">
                      {t(`phase34.blockKind.${item.kind}`)}
                    </p>
                    <p className="text-muted mt-1 text-sm">
                      {t(item.detailKey, { target: item.targetRef })}
                    </p>
                    <p className="text-muted mt-1 font-mono text-xs">
                      {item.auditRef}
                    </p>
                  </div>
                  <Badge kind="neutral">{RECORDED_FINDING_LABEL}</Badge>
                </div>
              </article>
            ))}
            {snapshot.findings.length === 0 ? (
              <p className="text-muted text-sm">
                {NO_DIAGNOSTIC_FINDINGS_LABEL}
              </p>
            ) : null}
          </div>
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="fairness-audit-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase34.fairness.eyebrow")}</p>
              <h4>{t("phase34.fairness.title")}</h4>
            </div>
            <Badge kind="neutral">
              {t("phase34.fairness.threshold", {
                value: formatNumber(snapshot.fairness.threshold, {
                  maximumFractionDigits: 2,
                }),
              })}
            </Badge>
          </div>
          <div className="mt-4 space-y-2">
            {snapshot.fairness.groups.map((group) => (
              <div
                key={group.groupId}
                className="border-line bg-background/55 rounded-xl border p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <strong>{group.groupLabel}</strong>
                  <Badge
                    data-interaction-state={group.status.label}
                    kind="neutral"
                  >
                    {group.status.label.replaceAll("_", " ")}
                  </Badge>
                </div>
                <div className="mt-2 grid gap-2 text-sm md:grid-cols-3">
                  <span data-quantity-metric-id={group.primaryDelta.metric_id}>
                    <Quantity value={group.primaryDelta} variant="dense" />
                  </span>
                  <span>
                    {t("phase34.fairness.ratio", {
                      value: formatNumber(group.disparateImpactRatio, {
                        maximumFractionDigits: 2,
                      }),
                    })}
                  </span>
                  <span>
                    {t("phase34.fairness.ci", {
                      lower: formatNumber(group.ciLower, {
                        maximumFractionDigits: 2,
                      }),
                      upper: formatNumber(group.ciUpper, {
                        maximumFractionDigits: 2,
                      }),
                    })}
                  </span>
                  <span>
                    {t("phase34.fairness.calibration", {
                      value: formatNumber(group.calibrationDelta, {
                        maximumFractionDigits: 2,
                      }),
                    })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="harm-assessment-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase34.harm.eyebrow")}</p>
              <h4>{t("phase34.harm.title")}</h4>
            </div>
            <Badge kind="neutral">
              {displayOwnerLabel(
                snapshot.harm.euAiAct.riskClass,
                t("common.unknown"),
              )}
            </Badge>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            {(["humanOversight", "transparency", "redressPath"] as const).map(
              (key) => (
                <div key={key} className="compact-metric">
                  <span>{t(`phase34.harm.eu.${key}`)}</span>
                  <strong>
                    {snapshot.harm.euAiAct[key].label.replaceAll("_", " ")}
                  </strong>
                </div>
              ),
            )}
          </div>
          <div className="mt-4 space-y-2">
            {snapshot.harm.rows.map((row) => (
              <div
                key={row.id}
                className="border-line bg-background/55 rounded-xl border p-3 text-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{t(row.expectedHarm)}</p>
                    <p className="text-muted mt-1">{t(row.mitigation)}</p>
                  </div>
                  <Badge
                    data-interaction-state={row.status.label}
                    kind="neutral"
                  >
                    {row.status.label.replaceAll("_", " ")}
                  </Badge>
                </div>
                <p className="text-muted mt-2 text-xs">
                  {t("phase34.harm.rowMeta", {
                    likelihood: row.likelihood
                      ? t(`phase34.harm.likelihood.${row.likelihood}`)
                      : t("common.unknown"),
                    residual: row.residualRisk
                      ? t(`phase34.harm.residual.${row.residualRisk}`)
                      : t("common.unknown"),
                  })}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="embargo-overlay-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase34.embargo.eyebrow")}</p>
              <h4>{t("phase34.embargo.title")}</h4>
            </div>
            <Badge kind="neutral">
              {formatNumber(snapshot.embargo.masks.length)}
            </Badge>
          </div>
          <div className="mt-4 space-y-2">
            {snapshot.embargo.masks.map((mask) => (
              <div
                key={mask.auditRef}
                className="border-line bg-background/55 rounded-xl border p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">
                      {t("phase34.embargo.masked")}
                    </p>
                    <p className="text-muted mt-1 text-sm">
                      {t("phase34.embargo.meta", {
                        reason: mask.reasonCode,
                        skeleton: mask.skeletonRef,
                        unlock: mask.unlockAt
                          ? formatDate(mask.unlockAt)
                          : t("common.unavailable"),
                      })}
                    </p>
                    <p className="text-muted mt-1 font-mono text-xs">
                      {mask.auditRef}
                    </p>
                  </div>
                  <Badge
                    data-interaction-state={mask.status.label}
                    kind="neutral"
                  >
                    {t(`phase34.embargo.status.${mask.status.label}`)}
                  </Badge>
                </div>
              </div>
            ))}
            {snapshot.embargo.masks.length === 0 ? (
              <p className="text-muted text-sm">{t("phase34.embargo.empty")}</p>
            ) : null}
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="revocation-ledger-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase34.revocation.eyebrow")}</p>
              <h4>{t("phase34.revocation.title")}</h4>
            </div>
            <Badge
              kind="neutral"
              data-owner-decision-validity={
                snapshot.revocation.currentStatus ?? ""
              }
            >
              {displayOwnerLabel(
                snapshot.revocation.currentStatus,
                t("common.unavailable"),
              )}
            </Badge>
          </div>
          <div className="mt-4 space-y-2">
            {snapshot.revocation.chain.map((entry) => (
              <div
                key={`${entry.relation}-${entry.policyRef}`}
                className="border-line bg-background/55 rounded-xl border p-3 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <strong>{entry.policyRef}</strong>
                  <Badge
                    kind="neutral"
                    data-owner-decision-validity={entry.status ?? ""}
                  >
                    {displayOwnerLabel(entry.status, t("common.unavailable"))}
                  </Badge>
                </div>
                <p className="text-muted mt-1">
                  {t(`phase34.revocation.relation.${entry.relation}`)} /{" "}
                  {t(entry.reason)}
                </p>
                <p className="text-muted mt-1 text-xs">
                  {t("phase34.revocation.time", {
                    known: formatDate(entry.knownAt),
                    valid: formatDate(entry.validAt),
                  })}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section
        className="border-line bg-surface/80 rounded-2xl border p-4"
        data-testid="slow-review-mode-panel"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="eyebrow">{t("phase34.slowReview.eyebrow")}</p>
            <h4>{t("phase34.slowReview.title")}</h4>
          </div>
          <Badge kind="neutral">
            {t("phase34.slowReview.progress", {
              completed: formatNumber(snapshot.slowReview.completed),
              total: formatNumber(snapshot.slowReview.total),
            })}
          </Badge>
        </div>
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {snapshot.slowReview.requirements.map((requirement) => {
            const canAcknowledge =
              requirement.opened &&
              !requirement.acknowledged &&
              requirement.dwellSeconds >= requirement.minimumDwellSeconds;
            return (
              <div
                key={requirement.id}
                className="border-line bg-background/55 rounded-xl border p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">
                      {t(`phase34.slowReview.section.${requirement.id}`)}
                    </p>
                    <p className="text-muted mt-1 text-xs">
                      {t("phase34.slowReview.dwell", {
                        actual: formatNumber(requirement.dwellSeconds),
                        required: formatNumber(requirement.minimumDwellSeconds),
                      })}
                    </p>
                    <p className="text-muted mt-1 font-mono text-xs">
                      {requirement.auditRef}
                    </p>
                  </div>
                  <Badge kind="neutral">
                    {requirement.blocked ? "review pending" : "review recorded"}
                  </Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={requirement.opened}
                    onClick={() => markOpened(requirement.id)}
                  >
                    {t("phase34.slowReview.open")}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={!canAcknowledge}
                    onClick={() => acknowledge(requirement.id)}
                  >
                    {t("phase34.slowReview.acknowledge")}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
        <div className="border-line mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-3">
          <p className="text-muted text-sm">
            {t("phase34.auditTrail", {
              value: formatNumber(snapshot.auditTrail.length),
            })}
          </p>
        </div>
      </section>
    </section>
  );
}
