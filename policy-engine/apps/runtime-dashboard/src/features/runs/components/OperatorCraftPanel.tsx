import { useEffect, useMemo, useReducer, useState } from "react";
import type { SyntheticEvent } from "react";
import {
  BookmarkPlus,
  BookOpenCheck,
  CheckCircle2,
  MessageSquarePlus,
  ShieldCheck,
  SlidersHorizontal,
  WalletCards,
} from "lucide-react";

import type { RunInspectorSummary } from "@/features/runs/context/RunInspectorContext";
import { buildSignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";
import {
  buildOperatorCraftSnapshot,
  completeReadingOnboardingRun,
  completeReadingOnboardingStep,
  createEvidenceWalletItem,
  createReviewerAnnotation,
  OPERATOR_CRAFT_CHANGED_EVENT,
  readEvidenceWallet,
  readReadingOnboardingState,
  readReviewerAnnotations,
  readReviewerThresholdProfile,
  saveEvidenceWalletItem,
  saveReviewerAnnotation,
  setReviewerThreshold,
  startReadingOnboarding,
  type ReadingOnboardingStepId,
} from "@/features/runs/domain/operatorCraft";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  cn,
  formatDate,
  formatNumber,
  formatPercent,
} from "@/shared/lib/utils";
import { Badge, Button, Slider, Textarea } from "@polisyos/atlas-ui";

const MAX_VISIBLE_HIDDEN_CLAIMS = 3;

function useOperatorCraftVersion() {
  const [version, refresh] = useReducer((value: number) => value + 1, 0);

  useEffect(() => {
    const onChange = () => refresh();
    globalThis.addEventListener?.(OPERATOR_CRAFT_CHANGED_EVENT, onChange);
    return () => {
      globalThis.removeEventListener?.(OPERATOR_CRAFT_CHANGED_EVENT, onChange);
    };
  }, []);

  return [version, refresh] as const;
}

function StepBadge({ completed }: { completed: boolean }) {
  const { t } = useI18n();
  return (
    <Badge kind={completed ? "ok" : "neutral"}>
      {completed ? t("phase36.onboarding.done") : t("common.pending")}
    </Badge>
  );
}

export function OperatorCraftPanel({
  runId,
  summary,
}: {
  runId: string;
  summary: RunInspectorSummary;
}) {
  const { t } = useI18n();
  const [operatorCraftVersion, refreshOperatorCraft] =
    useOperatorCraftVersion();
  const [annotationBody, setAnnotationBody] = useState("");

  const packet = useMemo(
    () =>
      buildSignedPublicDecisionPacket({
        decisionScore: summary.decisionScore,
        decisionView: summary.decisionView,
        evidenceContext: summary.evidenceContext,
        governanceIssues: summary.governanceIssues,
        policyDesignCaseProjection: summary.run?.policy_design_case_projection,
        runId,
      }),
    [
      runId,
      summary.decisionScore,
      summary.decisionView,
      summary.evidenceContext,
      summary.governanceIssues,
      summary.run?.policy_design_case_projection,
    ],
  );

  const snapshot = useMemo(
    () =>
      buildOperatorCraftSnapshot({
        annotations: readReviewerAnnotations(runId),
        onboardingState: readReadingOnboardingState(runId),
        packet,
        runId,
        thresholdProfile: readReviewerThresholdProfile(),
        walletItems: readEvidenceWallet(),
      }),
    [operatorCraftVersion, packet, runId],
  );

  const firstTargetRef = snapshot.annotationTargets[0]?.ref ?? "";
  const [selectedTargetRef, setSelectedTargetRef] = useState(firstTargetRef);

  useEffect(() => {
    if (!selectedTargetRef && firstTargetRef) {
      setSelectedTargetRef(firstTargetRef);
    }
  }, [firstTargetRef, selectedTargetRef]);

  const selectedTarget =
    snapshot.annotationTargets.find(
      (target) => target.ref === selectedTargetRef,
    ) ??
    snapshot.annotationTargets[0] ??
    null;
  const savedWalletRefs = useMemo(
    () => new Set(snapshot.walletItems.map((item) => item.ref)),
    [snapshot.walletItems],
  );

  function handleThresholdChange([next]: number[]) {
    if (typeof next !== "number") {
      return;
    }
    setReviewerThreshold({
      next,
      packet,
      runId,
      sequence: snapshot.thresholdProfile.auditEvent ? 1 : 0,
    });
    completeReadingOnboardingStep({
      packet,
      runId,
      stepId: "set_threshold",
    });
    refreshOperatorCraft();
  }

  function handleAnnotationSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTarget || !annotationBody.trim()) {
      return;
    }
    const annotation = createReviewerAnnotation({
      body: annotationBody,
      existingCount: snapshot.annotations.length,
      packet,
      runId,
      target: selectedTarget,
    });
    saveReviewerAnnotation(annotation);
    completeReadingOnboardingStep({
      packet,
      runId,
      stepId: "annotate_snapshot",
    });
    setAnnotationBody("");
    refreshOperatorCraft();
  }

  function handleSaveEvidence(index: number) {
    const candidate = snapshot.walletCandidates[index];
    if (!candidate) {
      return;
    }
    const item = createEvidenceWalletItem({
      candidate,
      existingCount: snapshot.walletItems.length,
      packet,
      runId,
    });
    saveEvidenceWalletItem(item);
    completeReadingOnboardingStep({
      packet,
      runId,
      stepId: "save_evidence",
    });
    refreshOperatorCraft();
  }

  function handleOnboardingStep(stepId: ReadingOnboardingStepId) {
    if (stepId === "safe_approval") {
      if (!snapshot.onboarding.canApprove) {
        return;
      }
      completeReadingOnboardingRun({
        packet,
        runId,
      });
    } else {
      completeReadingOnboardingStep({
        packet,
        runId,
        stepId,
      });
    }
    refreshOperatorCraft();
  }

  return (
    <section
      className="space-y-4"
      data-testid="operator-craft-panel"
      data-authored-exempt="true"
      data-authored-exempt-reason="Operator craft panels are reviewer workflow chrome; persisted annotation bodies are user-authored audit notes."
    >
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("phase36.eyebrow")}</p>
          <h3>{t("phase36.title")}</h3>
          <p className="text-muted mt-2 max-w-3xl text-sm">
            {t("phase36.body")}
          </p>
        </div>
        <Badge kind={snapshot.onboarding.canApprove ? "ok" : "warn"}>
          {t("phase36.onboarding.progress", {
            completed: formatNumber(snapshot.onboarding.completedCount),
            total: formatNumber(snapshot.onboarding.totalCount),
          })}
        </Badge>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="operator-threshold-dial"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase36.threshold.eyebrow")}</p>
              <h4>{t("phase36.threshold.title")}</h4>
            </div>
            <span className="bg-accent/15 text-accent rounded-full p-2">
              <SlidersHorizontal className="size-4" />
            </span>
          </div>
          <div className="mt-4 space-y-4">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-muted text-sm">
                {t("phase36.threshold.value")}
              </span>
              <strong className="font-mono text-2xl">
                {formatPercent(snapshot.thresholdProfile.threshold, {
                  maximumFractionDigits: 0,
                })}
              </strong>
            </div>
            <Slider
              aria-label={t("phase36.threshold.title")}
              max={1}
              min={0}
              step={0.05}
              value={[snapshot.thresholdProfile.threshold]}
              onValueChange={handleThresholdChange}
              thumbLabels={[t("phase36.threshold.title")]}
            />
            <div className="grid gap-2 text-sm md:grid-cols-3">
              <div className="border-line bg-background/55 rounded-xl border p-3">
                <span className="text-muted block text-xs">
                  {t("phase36.threshold.visible")}
                </span>
                <strong>
                  {formatNumber(snapshot.thresholdImpact.visibleCount)}
                </strong>
              </div>
              <div className="border-line bg-background/55 rounded-xl border p-3">
                <span className="text-muted block text-xs">
                  {t("phase36.threshold.hidden")}
                </span>
                <strong>
                  {formatNumber(snapshot.thresholdImpact.hiddenCount)}
                </strong>
              </div>
              <div className="border-line bg-background/55 rounded-xl border p-3">
                <span className="text-muted block text-xs">
                  {t("phase36.threshold.remaining")}
                </span>
                <strong>
                  {formatPercent(snapshot.thresholdImpact.remainingShare)}
                </strong>
              </div>
            </div>
            <div className="space-y-2">
              {snapshot.thresholdImpact.hiddenClaims.length > 0 ? (
                snapshot.thresholdImpact.hiddenClaims
                  .slice(0, MAX_VISIBLE_HIDDEN_CLAIMS)
                  .map((claim, index) => (
                    <div
                      key={`${claim.targetRef}:${index}`}
                      className="border-line bg-background/55 flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-sm"
                    >
                      <span className="min-w-0 truncate">{claim.label}</span>
                      <span className="text-muted font-mono">
                        {formatPercent(claim.score)}
                      </span>
                    </div>
                  ))
              ) : (
                <p className="text-muted text-sm">
                  {t("phase36.threshold.noHidden")}
                </p>
              )}
            </div>
            <p className="text-muted text-xs">
              {t("phase36.threshold.updated", {
                date: formatDate(snapshot.thresholdProfile.updatedAt),
              })}
            </p>
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="annotation-surface-panel"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase36.annotations.eyebrow")}</p>
              <h4>{t("phase36.annotations.title")}</h4>
            </div>
            <span className="bg-accent/15 text-accent rounded-full p-2">
              <MessageSquarePlus className="size-4" />
            </span>
          </div>
          <form className="mt-4 space-y-3" onSubmit={handleAnnotationSubmit}>
            <label className="grid gap-2 text-sm">
              <span className="text-muted">
                {t("phase36.annotations.target")}
              </span>
              <select
                className="atlas-input"
                value={selectedTarget?.ref ?? ""}
                onChange={(event) => setSelectedTargetRef(event.target.value)}
              >
                {snapshot.annotationTargets.map((target) => (
                  <option key={target.ref} value={target.ref}>
                    {target.label}
                  </option>
                ))}
              </select>
            </label>
            <Textarea
              className="min-h-24"
              placeholder={t("phase36.annotations.placeholder")}
              value={annotationBody}
              onChange={(event) => setAnnotationBody(event.target.value)}
            />
            <Button
              type="submit"
              leading={<MessageSquarePlus className="size-4" />}
              size="sm"
              variant="primary"
              disabled={!selectedTarget || !annotationBody.trim()}
            >
              {t("phase36.annotations.add")}
            </Button>
          </form>
          <div className="mt-4 space-y-2">
            {snapshot.annotations.length > 0 ? (
              snapshot.annotations.map((annotation) => (
                <article
                  key={annotation.id}
                  className="border-line bg-background/55 rounded-xl border p-3 text-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <strong>{annotation.target.label}</strong>
                    <Badge kind="neutral">
                      {t("phase36.annotations.snapshot", {
                        hash: annotation.snapshot.packetHash,
                      })}
                    </Badge>
                  </div>
                  <p className="mt-2 leading-6">{annotation.body}</p>
                </article>
              ))
            ) : (
              <p className="text-muted text-sm">
                {t("phase36.annotations.empty")}
              </p>
            )}
          </div>
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="evidence-wallet-panel"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase36.wallet.eyebrow")}</p>
              <h4>{t("phase36.wallet.title")}</h4>
            </div>
            <span className="bg-accent/15 text-accent rounded-full p-2">
              <WalletCards className="size-4" />
            </span>
          </div>
          <div className="mt-4 grid gap-3">
            {snapshot.walletCandidates.slice(0, 5).map((candidate, index) => {
              const saved = savedWalletRefs.has(candidate.ref);
              return (
                <article
                  key={candidate.ref}
                  className="border-line bg-background/55 rounded-xl border p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <strong className="text-sm">{candidate.label}</strong>
                      <p className="text-muted mt-1 text-xs leading-5">
                        {candidate.summary}
                      </p>
                    </div>
                    <Button
                      type="button"
                      leading={
                        saved ? (
                          <CheckCircle2 className="size-4" />
                        ) : (
                          <BookmarkPlus className="size-4" />
                        )
                      }
                      size="sm"
                      variant={saved ? "ghost" : "primary"}
                      disabled={saved}
                      onClick={() => handleSaveEvidence(index)}
                    >
                      {saved
                        ? t("phase36.wallet.saved")
                        : t("phase36.wallet.save")}
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
          <div className="mt-4 space-y-2">
            <p className="text-muted text-xs font-semibold tracking-wide uppercase">
              {t("phase36.wallet.savedTitle")}
            </p>
            {snapshot.walletItems.length > 0 ? (
              snapshot.walletItems.map((item) => (
                <div
                  key={item.id}
                  className="border-line bg-background/55 flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-sm"
                >
                  <span className="min-w-0 truncate">{item.label}</span>
                  <span className="text-muted font-mono">{item.ref}</span>
                </div>
              ))
            ) : (
              <p className="text-muted text-sm">{t("phase36.wallet.empty")}</p>
            )}
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="reading-onboarding-panel"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase36.onboarding.eyebrow")}</p>
              <h4>{t("phase36.onboarding.title")}</h4>
            </div>
            <span className="bg-accent/15 text-accent rounded-full p-2">
              <BookOpenCheck className="size-4" />
            </span>
          </div>
          <div className="mt-4 space-y-3">
            <div
              aria-hidden="true"
              className="bg-line h-2 overflow-hidden rounded-full"
            >
              <div
                className="bg-accent h-full rounded-full"
                style={{
                  width: formatPercent(snapshot.onboarding.progress, {
                    maximumFractionDigits: 0,
                  }),
                }}
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-muted text-sm">
                {t("phase36.onboarding.progress", {
                  completed: formatNumber(snapshot.onboarding.completedCount),
                  total: formatNumber(snapshot.onboarding.totalCount),
                })}
              </span>
              <Button
                type="button"
                leading={<ShieldCheck className="size-4" />}
                size="sm"
                variant="ghost"
                onClick={() => {
                  startReadingOnboarding({ runId });
                  refreshOperatorCraft();
                }}
              >
                {t("phase36.onboarding.start")}
              </Button>
            </div>
            <div className="space-y-2">
              {snapshot.onboarding.steps.map((step) => (
                <div
                  key={step.id}
                  className={cn(
                    "border-line bg-background/55 flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-sm",
                    step.completed && "border-accent/20 bg-accent/5",
                  )}
                >
                  <div className="min-w-0">
                    <strong className="block truncate">
                      {t(`phase36.onboarding.step.${step.id}`)}
                    </strong>
                    <span className="text-muted block truncate font-mono text-xs">
                      {step.evidenceRef}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <StepBadge completed={step.completed} />
                    {!step.completed ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={
                          step.id === "safe_approval" &&
                          !snapshot.onboarding.canApprove
                        }
                        onClick={() => handleOnboardingStep(step.id)}
                      >
                        {t("phase36.onboarding.complete")}
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
            {snapshot.onboarding.timeToFirstSafeApprovalSeconds !== null ? (
              <p className="text-muted text-sm">
                {t("phase36.onboarding.ttv", {
                  seconds: formatNumber(
                    snapshot.onboarding.timeToFirstSafeApprovalSeconds,
                  ),
                })}
              </p>
            ) : null}
          </div>
        </section>
      </div>
    </section>
  );
}
