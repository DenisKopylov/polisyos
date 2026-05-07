import { useEffect, useMemo, useReducer } from "react";
import { Activity, Radio, SlidersHorizontal, TimerReset } from "lucide-react";

import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";
import type { RunInspectorSummary } from "@/features/runs/context/RunInspectorContext";
import {
  completeReadingOnboardingStep,
  OPERATOR_CRAFT_CHANGED_EVENT,
  readReviewerThresholdProfile,
  setReviewerThreshold,
} from "@/features/runs/domain/operatorCraft";
import { buildSignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatDate, formatNumber, formatPercent } from "@/shared/lib/utils";
import { Badge, Slider } from "@/shared/ui";

export function AmbientTelemetryHud({
  activeTab,
  runId,
  summary,
}: {
  activeTab: string;
  runId: string;
  summary: RunInspectorSummary;
}) {
  const { t } = useI18n();
  const temporalCursor = useMaybeTemporalCursor();
  const { flags, source, status } = useFeatureFlags();
  const [operatorCraftVersion, refreshOperatorCraft] = useReducer(
    (value: number) => value + 1,
    0,
  );
  const enabledFlagCount = Object.values(flags).filter(Boolean).length;
  const effectiveScope = temporalCursor?.effectiveScope ?? null;
  const thresholdProfile = useMemo(
    () => readReviewerThresholdProfile(),
    [operatorCraftVersion],
  );
  const packet = useMemo(
    () =>
      buildSignedPublicDecisionPacket({
        decisionScore: summary.decisionScore,
        decisionView: summary.decisionView,
        evidenceContext: summary.evidenceContext,
        governanceIssues: summary.governanceIssues,
        runId,
      }),
    [
      runId,
      summary.decisionScore,
      summary.decisionView,
      summary.evidenceContext,
      summary.governanceIssues,
    ],
  );

  useEffect(() => {
    const onChange = () => refreshOperatorCraft();
    globalThis.addEventListener?.(OPERATOR_CRAFT_CHANGED_EVENT, onChange);
    return () => {
      globalThis.removeEventListener?.(OPERATOR_CRAFT_CHANGED_EVENT, onChange);
    };
  }, []);

  function handleThresholdChange([next]: number[]) {
    if (typeof next !== "number") {
      return;
    }
    setReviewerThreshold({
      next,
      packet,
      runId,
      sequence: thresholdProfile.auditEvent ? 1 : 0,
    });
    completeReadingOnboardingStep({
      packet,
      runId,
      stepId: "set_threshold",
    });
    refreshOperatorCraft();
  }

  return (
    <aside
      aria-label={t("phase32.telemetry.title")}
      className="border-line bg-panel/95 shadow-panel fixed right-4 bottom-4 z-40 hidden max-w-[22rem] rounded-2xl border p-3 backdrop-blur md:block"
      data-testid="ambient-telemetry-hud"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="bg-accent/15 text-accent rounded-full p-1.5">
            <Activity className="size-4" />
          </span>
          <div>
            <p className="text-sm font-semibold">
              {t("phase32.telemetry.title")}
            </p>
            <p className="text-muted font-mono text-[11px]">{runId}</p>
          </div>
        </div>
        <Badge kind={summary.liveTransport ? "info" : "warn"}>
          {summary.liveTransport
            ? t("phase32.telemetry.live")
            : t("phase32.telemetry.degraded")}
        </Badge>
      </div>

      <div className="mt-3 grid gap-2 text-xs">
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted inline-flex items-center gap-1">
            <Radio className="size-3" />
            {t("phase32.telemetry.transport")}
          </span>
          <strong>{summary.transportStatus}</strong>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted inline-flex items-center gap-1">
            <TimerReset className="size-3" />
            {t("phase32.telemetry.scope")}
          </span>
          <strong>
            {effectiveScope?.validAt
              ? formatDate(effectiveScope.validAt)
              : t("phase32.telemetry.now")}
          </strong>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted">{t("phase32.telemetry.flags")}</span>
          <strong>
            {t("phase32.telemetry.flagCount", {
              value: formatNumber(enabledFlagCount),
              source,
              status,
            })}
          </strong>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted">{t("phase32.telemetry.surface")}</span>
          <strong>{activeTab}</strong>
        </div>
        <div
          className="border-line bg-background/55 mt-1 rounded-xl border p-2"
          data-testid="ambient-trust-threshold"
        >
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="text-muted inline-flex items-center gap-1">
              <SlidersHorizontal className="size-3" />
              {t("phase36.threshold.short")}
            </span>
            <strong>
              {formatPercent(thresholdProfile.threshold, {
                maximumFractionDigits: 0,
              })}
            </strong>
          </div>
          <Slider
            aria-label={t("phase36.threshold.title")}
            max={1}
            min={0}
            step={0.05}
            value={[thresholdProfile.threshold]}
            onValueChange={handleThresholdChange}
            thumbLabels={[t("phase36.threshold.title")]}
          />
        </div>
      </div>
    </aside>
  );
}
