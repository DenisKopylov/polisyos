import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { RunLaunchResponse } from "@polisyos/runtime-api-client";

import { useCapabilities } from "@/api/hooks/useCapabilities";
import { useLlmProfiles } from "@/api/hooks/useLlmProfiles";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  isExecutionPolicyEnabled,
  readExecutionPolicyConstraint,
} from "@/shared/lib/capabilities";
import { cn, formatNumber } from "@/shared/lib/utils";
import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";
import { Badge, Button } from "@polisyos/atlas-ui";
import { ProvenanceStrip } from "@/shared/ui";
import { parseComposerSearchParams } from "../domain/searchParams";
import { launchStatusTone } from "../domain/launchPresentation";
import {
  NaturalLanguageComposerSection,
  WorkflowComposerSection,
} from "./ComposerModeSections";

type Mode = "workflow" | "nl";
type RecentLaunch = { runId: string; status: RunLaunchResponse["status"] };

const composerHeroProvenance: ProvenanceItem[] = [
  {
    id: "intervention",
    glyph: "intervention",
    label: "Interventions",
  },
  {
    id: "evidence",
    glyph: "evidence",
    label: "Evidence",
  },
  {
    id: "governance",
    glyph: "governance-pass",
    label: "Guardrails",
  },
];

function ComposerSummaryMetric({
  label,
  value,
  tone = "default",
}: {
  label: string;
  tone?: "default" | "accent";
  value: string;
}) {
  return (
    <div
      className={cn(
        "rounded-[24px] border p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)]",
        tone === "accent"
          ? "border-[rgba(28,139,130,0.18)] bg-[linear-gradient(180deg,rgba(28,139,130,0.15),rgba(255,255,255,0.74))]"
          : "border-[rgba(23,25,29,0.08)] bg-white/70",
      )}
    >
      <span className="text-muted block text-xs tracking-[0.12em] uppercase">
        {label}
      </span>
      <strong className="mt-2 block text-2xl font-semibold tracking-[-0.04em]">
        {value}
      </strong>
    </div>
  );
}

function ComposerJourneyStep({
  active,
  body,
  index,
  title,
}: {
  active: boolean;
  body: string;
  index: number;
  title: string;
}) {
  return (
    <div
      className={cn(
        "rounded-full border px-4 py-3 transition-colors",
        active
          ? "border-transparent bg-[linear-gradient(135deg,#26313a,#1a1f24)] text-[#fff8ef] shadow-[0_16px_28px_rgba(23,25,29,0.14)]"
          : "text-text border-[rgba(23,25,29,0.08)] bg-white/62",
      )}
    >
      <span
        className={cn(
          "block text-[11px] font-semibold tracking-[0.14em] uppercase",
          active ? "text-white/64" : "text-muted",
        )}
      >
        {index}
      </span>
      <strong className="mt-2 block text-sm">{title}</strong>
      <p
        className={cn(
          "mt-1 text-xs leading-5",
          active ? "text-white/78" : "text-muted",
        )}
      >
        {body}
      </p>
    </div>
  );
}

function ComposerGuardrailRow({
  kind,
  label,
  value,
}: {
  kind: "ok" | "warn" | "neutral";
  label: string;
  value: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[18px] border border-[rgba(23,25,29,0.06)] bg-white/58 px-4 py-3">
      <span className="text-sm font-semibold">{label}</span>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted font-mono text-[11px] tracking-[0.08em] uppercase">
          {value}
        </span>
        <Badge kind={kind} className="px-2 py-1 text-[10px]">
          {value}
        </Badge>
      </div>
    </div>
  );
}

function ComposerRailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-b border-white/10 pb-3 last:border-b-0 last:pb-0">
      <span className="block font-mono text-[11px] tracking-[0.12em] text-white/52 uppercase">
        {label}
      </span>
      <strong className="mt-1 block text-base font-semibold text-[#fff8ef]">
        {value}
      </strong>
    </div>
  );
}

function ComposerRecentLaunchRail({
  recentLaunches,
}: {
  recentLaunches: RecentLaunch[];
}) {
  const { t } = useI18n();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-[11px] tracking-[0.12em] text-white/52 uppercase">
          {t("pages.composer.recentLaunches")}
        </p>
        <Badge kind="neutral" className="bg-white/10 text-white/72">
          {formatNumber(recentLaunches.length)}
        </Badge>
      </div>
      {recentLaunches.length === 0 ? (
        <p className="text-sm leading-6 text-white/72">
          {t("pages.composer.noLaunchReceipts")}
        </p>
      ) : (
        <div className="space-y-2">
          {recentLaunches.slice(0, 3).map((launch) => (
            <div
              key={launch.runId}
              className="flex items-center justify-between gap-3 rounded-[18px] border border-white/10 bg-white/5 px-3 py-3"
            >
              <span className="font-mono text-xs text-white/78">
                {launch.runId}
              </span>
              <Badge
                kind={launchStatusTone(launch.status)}
                className="px-2 py-1 text-[10px]"
              >
                {launch.status}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function LaunchRunPage() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const capabilitiesQuery = useCapabilities();
  const llmProfilesQuery = useLlmProfiles();
  const composerSearch = parseComposerSearchParams(searchParams);
  const fromRunId = composerSearch.fromRun;
  const [mode, setMode] = useState<Mode>(
    () => composerSearch.mode ?? (fromRunId ? "workflow" : "nl"),
  );
  const [recentLaunches, setRecentLaunches] = useState<RecentLaunch[]>([]);

  const executionPolicyManifest = capabilitiesQuery.data;
  const llmProfiles = llmProfilesQuery.data?.profiles ?? [];
  const multimodelEnabled = isExecutionPolicyEnabled(
    executionPolicyManifest,
    "multimodel_nl",
  );
  const preflightEnabled = isExecutionPolicyEnabled(
    executionPolicyManifest,
    "required_preflight",
  );
  const autoMaterializationEnabled = isExecutionPolicyEnabled(
    executionPolicyManifest,
    "auto_materialization",
  );
  const maxParallelConstraint = readExecutionPolicyConstraint(
    executionPolicyManifest,
    "max_parallel_models",
    4,
  );
  const maxIterationsConstraint = readExecutionPolicyConstraint(
    executionPolicyManifest,
    "max_nl_iterations",
    5,
  );
  const journeySteps = useMemo(
    () => [
      {
        body: t("pages.composer.stepBodies.workflow"),
        id: "workflow",
        title: t("pages.composer.steps.workflow"),
      },
      {
        body: t("pages.composer.stepBodies.nl"),
        id: "nl",
        title: t("pages.composer.steps.nl"),
      },
      {
        body: t("pages.composer.stepBodies.evidence"),
        id: "evidence",
        title: t("pages.composer.steps.evidence"),
      },
      {
        body: t("pages.composer.stepBodies.guardrails"),
        id: "guardrails",
        title: t("pages.composer.steps.guardrails"),
      },
      {
        body: t("pages.composer.stepBodies.launch"),
        id: "launch",
        title: t("pages.composer.steps.launch"),
      },
    ],
    [t],
  );
  const guardrailRows = useMemo<
    Array<{ kind: "ok" | "warn" | "neutral"; label: string; value: string }>
  >(
    () => [
      {
        kind: preflightEnabled ? "ok" : ("warn" as const),
        label: t("pages.composer.plan"),
        value: preflightEnabled
          ? t("pages.composer.preflightRequired")
          : t("pages.composer.preflightOptional"),
      },
      {
        kind: multimodelEnabled ? "ok" : ("neutral" as const),
        label: t("pages.composer.maxParallelModels"),
        value: multimodelEnabled
          ? formatNumber(maxParallelConstraint)
          : t("common.disabled"),
      },
      {
        kind: autoMaterializationEnabled ? "ok" : ("neutral" as const),
        label: t("pages.composer.capabilityContext"),
        value: autoMaterializationEnabled
          ? t("common.enabled")
          : t("common.disabled"),
      },
      {
        kind: "neutral" as const,
        label: t("pages.composer.maxIterations"),
        value: formatNumber(maxIterationsConstraint),
      },
    ],
    [
      autoMaterializationEnabled,
      maxIterationsConstraint,
      maxParallelConstraint,
      multimodelEnabled,
      preflightEnabled,
      t,
    ],
  );
  const launchContextSummary = fromRunId
    ? fromRunId
    : t("pages.composer.newScenario");

  function addRecentLaunch(runId: string, status: RunLaunchResponse["status"]) {
    setRecentLaunches((previous) =>
      [{ runId, status }, ...previous].slice(0, 5),
    );
  }

  return (
    <div className="space-y-5" data-testid="composer-page">
      <h1 className="sr-only">{t("pages.composer.title")}</h1>

      <section className="relative overflow-hidden rounded-[30px] border border-[rgba(23,25,29,0.08)] bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(247,243,235,0.94))] p-5 shadow-[0_26px_50px_rgba(23,25,29,0.08)] md:p-6">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-48 bg-[radial-gradient(circle_at_top_left,rgba(28,139,130,0.18),transparent_36%),radial-gradient(circle_at_top_right,rgba(181,139,43,0.14),transparent_32%)]" />
        <div className="relative grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.8fr)]">
          <div className="space-y-5">
            <div className="space-y-4">
              <ProvenanceStrip
                title={t("pages.composer.title")}
                items={composerHeroProvenance}
                density="compact"
              />

              <div className="space-y-3">
                <h2 className="max-w-3xl text-[clamp(2rem,4vw,3.25rem)] leading-[0.96] font-extrabold tracking-[-0.05em]">
                  {t("pages.composer.heroTitle")}
                </h2>
                <p className="topbar-subtitle max-w-3xl">
                  {t("pages.composer.journeyTitle")}
                </p>
              </div>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
                <div className="rounded-[28px] border border-[rgba(23,25,29,0.08)] bg-[linear-gradient(145deg,rgba(28,139,130,0.14),rgba(181,139,43,0.08)),rgba(255,255,255,0.72)] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)]">
                  <p className="eyebrow">
                    {t("pages.composer.steps.workflow")}
                  </p>
                  <p className="text-text mt-3 text-lg leading-8 font-semibold tracking-[-0.03em]">
                    {fromRunId
                      ? t("pages.composer.replanIntent", { runId: fromRunId })
                      : mode === "workflow"
                        ? t("pages.composer.modeWorkflowBody")
                        : t("pages.composer.modeNlBody")}
                  </p>
                  <p className="text-muted mt-4 max-w-2xl text-sm leading-6">
                    {fromRunId
                      ? t("pages.composer.journeyReplanBody", {
                          runId: fromRunId,
                        })
                      : t("pages.composer.journeyBody")}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                  <ComposerSummaryMetric
                    label={t("pages.composer.journeyMetrics.mode")}
                    value={
                      mode === "workflow"
                        ? t("pages.composer.workflow")
                        : t("pages.composer.naturalLanguage")
                    }
                    tone="accent"
                  />
                  <ComposerSummaryMetric
                    label={t("pages.composer.journeyMetrics.models")}
                    value={formatNumber(llmProfiles.length)}
                  />
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                data-testid="composer-mode-workflow"
                onClick={() => setMode("workflow")}
                variant={mode === "workflow" ? "primary" : "ghost"}
              >
                {t("pages.composer.workflow")}
              </Button>
              <Button
                type="button"
                data-testid="composer-mode-nl"
                onClick={() => setMode("nl")}
                variant={mode === "nl" ? "primary" : "ghost"}
              >
                {t("pages.composer.naturalLanguage")}
              </Button>
            </div>

            <div>
              <div className="rounded-[28px] border border-[rgba(23,25,29,0.08)] bg-white/58 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)]">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="eyebrow">
                      {t("pages.composer.governanceConstraints")}
                    </p>
                    <h3 className="text-xl font-semibold tracking-[-0.03em]">
                      {mode === "workflow"
                        ? t("pages.composer.modeWorkflowTitle")
                        : t("pages.composer.modeNlTitle")}
                    </h3>
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  {guardrailRows.map((row) => (
                    <ComposerGuardrailRow key={row.label} {...row} />
                  ))}
                </div>
                <p className="text-muted mt-4 text-sm leading-6">
                  {t("pages.composer.dynamicTextPolicy")}
                </p>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-5">
              {journeySteps.map((step, index) => {
                const isActive =
                  (step.id === "workflow" && mode === "workflow") ||
                  (step.id === "nl" && mode === "nl") ||
                  (step.id !== "workflow" && step.id !== "nl");

                return (
                  <ComposerJourneyStep
                    key={step.id}
                    active={isActive}
                    body={step.body}
                    index={index + 1}
                    title={step.title}
                  />
                );
              })}
            </div>
          </div>

          <aside className="flex h-full flex-col gap-5 rounded-[28px] bg-[linear-gradient(180deg,rgba(38,49,58,0.98),rgba(20,22,26,0.96))] p-6 text-[#f5f0e6] shadow-[0_26px_40px_rgba(23,25,29,0.18)]">
            <div className="space-y-4">
              <ComposerRailStat
                label={t("pages.composer.journeyMetrics.mode")}
                value={
                  mode === "workflow"
                    ? t("pages.composer.workflow")
                    : t("pages.composer.naturalLanguage")
                }
              />
              <ComposerRailStat
                label={t("pages.composer.journeyMetrics.models")}
                value={formatNumber(llmProfiles.length)}
              />
              <ComposerRailStat
                label={t("pages.composer.steps.launch")}
                value={launchContextSummary}
              />
            </div>

            <ComposerRecentLaunchRail recentLaunches={recentLaunches} />
          </aside>
        </div>
      </section>

      {mode === "workflow" ? (
        <WorkflowComposerSection
          autoMaterializationEnabled={autoMaterializationEnabled}
          fromRunId={fromRunId}
          onLaunchCreated={addRecentLaunch}
          preflightEnabled={preflightEnabled}
          recentLaunches={recentLaunches}
        />
      ) : (
        <NaturalLanguageComposerSection
          autoMaterializationEnabled={autoMaterializationEnabled}
          fromRunId={fromRunId}
          llmProfiles={llmProfiles}
          llmProfilesError={llmProfilesQuery.error}
          llmProfilesLoading={llmProfilesQuery.isLoading}
          maxIterationsConstraint={maxIterationsConstraint}
          maxParallelConstraint={maxParallelConstraint}
          multimodelEnabled={multimodelEnabled}
          onLaunchCreated={addRecentLaunch}
          preflightEnabled={preflightEnabled}
          recentLaunches={recentLaunches}
        />
      )}
    </div>
  );
}
