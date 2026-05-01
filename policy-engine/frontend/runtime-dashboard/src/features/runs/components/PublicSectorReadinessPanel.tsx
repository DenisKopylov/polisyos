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
  type ReadinessSeverity,
  type StakeholderLens,
  STAKEHOLDER_LENSES,
  writeStoredReviewAttention,
} from "@/features/runs/domain/publicSectorReadiness";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn, formatDate, formatNumber } from "@/lib/utils";
import { Badge, Button } from "@/shared/ui";

function statusKind(status: ReadinessSeverity) {
  if (status === "pass") return "ok";
  if (status === "warn") return "warn";
  return "fail";
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
        <Badge kind={snapshot.approvalReady ? "ok" : "fail"}>
          {snapshot.approvalReady
            ? t("phase34.approval.ready")
            : t("phase34.approval.blocked", {
                value: formatNumber(snapshot.blocks.length),
              })}
        </Badge>
      </div>

      {snapshot.fairness.sentinel ? (
        <div
          className="border-danger/45 bg-danger/10 rounded-2xl border p-3"
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
            <Badge kind="fail">{snapshot.fairness.sentinel.auditRef}</Badge>
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
              <p className="eyebrow">{t("phase34.blockers.eyebrow")}</p>
              <h4>{t("phase34.blockers.title")}</h4>
            </div>
            <Badge kind={snapshot.blocks.length > 0 ? "fail" : "ok"}>
              {formatNumber(snapshot.blocks.length)}
            </Badge>
          </div>
          <div className="mt-4 space-y-2">
            {snapshot.blocks.map((item) => (
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
                  <Badge kind="fail">{t("phase34.approval.block")}</Badge>
                </div>
              </article>
            ))}
            {snapshot.blocks.length === 0 ? (
              <p className="text-muted text-sm">
                {t("phase34.blockers.empty")}
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
            <Badge kind={snapshot.fairness.blocked ? "fail" : "ok"}>
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
                  <Badge kind={statusKind(group.status)}>
                    {t(`phase34.status.${group.status}`)}
                  </Badge>
                </div>
                <div className="mt-2 grid gap-2 text-sm md:grid-cols-3">
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
            <Badge kind={snapshot.harm.blocked ? "fail" : "ok"}>
              {t(`phase34.harm.risk.${snapshot.harm.euAiAct.riskClass}`)}
            </Badge>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            {(["humanOversight", "transparency", "redressPath"] as const).map(
              (key) => (
                <div key={key} className="compact-metric">
                  <span>{t(`phase34.harm.eu.${key}`)}</span>
                  <strong>
                    {t(`phase34.status.${snapshot.harm.euAiAct[key]}`)}
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
                  <Badge kind={statusKind(row.status)}>
                    {t(`phase34.status.${row.status}`)}
                  </Badge>
                </div>
                <p className="text-muted mt-2 text-xs">
                  {t("phase34.harm.rowMeta", {
                    likelihood: t(`phase34.harm.likelihood.${row.likelihood}`),
                    residual: t(`phase34.harm.residual.${row.residualRisk}`),
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
            <Badge kind={snapshot.embargo.blocked ? "fail" : "ok"}>
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
                  <Badge kind={mask.status === "active" ? "fail" : "warn"}>
                    {t(`phase34.embargo.status.${mask.status}`)}
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
            <Badge kind={snapshot.revocation.blocked ? "fail" : "ok"}>
              {t(
                `phase34.revocation.status.${snapshot.revocation.currentStatus}`,
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
                  <Badge kind={entry.status === "active" ? "ok" : "warn"}>
                    {t(`phase34.revocation.entryStatus.${entry.status}`)}
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
          <Badge kind={snapshot.slowReview.blocked ? "fail" : "ok"}>
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
                  <Badge kind={requirement.blocked ? "fail" : "ok"}>
                    {requirement.blocked
                      ? t("phase34.approval.block")
                      : t("phase34.approval.ready")}
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
          <Button
            type="button"
            disabled={!snapshot.approvalReady}
            variant={snapshot.approvalReady ? "primary" : "ghost"}
          >
            {t("phase34.approval.action")}
          </Button>
        </div>
      </section>
    </section>
  );
}
