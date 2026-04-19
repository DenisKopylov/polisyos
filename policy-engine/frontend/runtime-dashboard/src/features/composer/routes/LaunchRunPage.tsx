import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useCapabilities } from "@/api/hooks/useCapabilities";
import { useLlmProfiles } from "@/api/hooks/useLlmProfiles";
import { useI18n } from "@/i18n/LocaleProvider";
import {
  getCapability,
  isCapabilityEnabled,
  readNumericConstraint,
} from "@/lib/capabilities";
import { cn, formatNumber } from "@/lib/utils";
import { Button, Card } from "@/shared/ui";
import { parseComposerSearchParams } from "../domain/searchParams";
import {
  NaturalLanguageComposerSection,
  WorkflowComposerSection,
} from "./ComposerModeSections";

type Mode = "workflow" | "nl";

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
  const [recentLaunches, setRecentLaunches] = useState<
    Array<{ runId: string; status: string }>
  >([]);

  const manifest = capabilitiesQuery.data;
  const llmProfiles = llmProfilesQuery.data?.profiles ?? [];
  const multimodelEnabled = isCapabilityEnabled(manifest, "multimodel_nl");
  const preflightEnabled = isCapabilityEnabled(manifest, "required_preflight");
  const autoMaterializationEnabled = isCapabilityEnabled(
    manifest,
    "auto_materialization",
  );
  const maxParallelConstraint = readNumericConstraint(
    manifest,
    "max_parallel_models",
    4,
  );
  const maxIterationsConstraint = readNumericConstraint(
    manifest,
    "max_nl_iterations",
    5,
  );
  const capabilityHighlights = useMemo(
    () =>
      [
        getCapability(manifest, "multimodel_nl"),
        getCapability(manifest, "required_preflight"),
        getCapability(manifest, "auto_materialization"),
        getCapability(manifest, "promotion_lane"),
      ].filter((feature): feature is NonNullable<typeof feature> =>
        Boolean(feature),
      ),
    [manifest],
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

  function addRecentLaunch(runId: string, status: string) {
    setRecentLaunches((previous) =>
      [{ runId, status }, ...previous].slice(0, 5),
    );
  }

  return (
    <div className="space-y-5" data-testid="composer-page">
      <h1 className="sr-only">{t("pages.composer.title")}</h1>

      <Card className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
          <div>
            <p className="eyebrow">{t("pages.composer.title")}</p>
            <h2>{t("pages.composer.heroTitle")}</h2>
            <p className="topbar-subtitle">
              {t("pages.composer.journeyTitle")}
            </p>
            <p className="text-muted mt-2 max-w-3xl text-sm">
              {fromRunId
                ? t("pages.composer.journeyReplanBody", { runId: fromRunId })
                : t("pages.composer.journeyBody")}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <span className="text-muted text-xs tracking-wide uppercase">
                {t("pages.composer.journeyMetrics.mode")}
              </span>
              <strong className="mt-2 block text-lg font-semibold">
                {mode === "workflow"
                  ? t("pages.composer.workflow")
                  : t("pages.composer.naturalLanguage")}
              </strong>
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <span className="text-muted text-xs tracking-wide uppercase">
                {t("pages.composer.journeyMetrics.capabilities")}
              </span>
              <strong className="mt-2 block text-lg font-semibold">
                {formatNumber(capabilityHighlights.length)}
              </strong>
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <span className="text-muted text-xs tracking-wide uppercase">
                {t("pages.composer.journeyMetrics.models")}
              </span>
              <strong className="mt-2 block text-lg font-semibold">
                {formatNumber(llmProfiles.length)}
              </strong>
            </div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-5">
          {journeySteps.map((step, index) => {
            const isActive =
              (step.id === "workflow" && mode === "workflow") ||
              (step.id === "nl" && mode === "nl") ||
              (step.id !== "workflow" && step.id !== "nl");

            return (
              <div
                key={step.id}
                className={cn(
                  "rounded-2xl border px-3 py-4",
                  isActive
                    ? "border-accent/35 bg-accent/10"
                    : "bg-surface/75 border-line",
                )}
              >
                <span className="text-muted block text-xs tracking-wide uppercase">
                  {index + 1}
                </span>
                <strong className="mt-2 block text-sm">{step.title}</strong>
                <p className="text-muted mt-2 text-xs">{step.body}</p>
              </div>
            );
          })}
        </div>

        <div className="bg-surface/70 border-line flex flex-wrap items-center justify-between gap-4 rounded-2xl border p-4">
          <div>
            <p className="eyebrow">{t("pages.composer.modeTitle")}</p>
            <h3 className="text-lg font-semibold">
              {mode === "workflow"
                ? t("pages.composer.modeWorkflowTitle")
                : t("pages.composer.modeNlTitle")}
            </h3>
            <p className="text-muted mt-2 text-sm">
              {mode === "workflow"
                ? t("pages.composer.modeWorkflowBody")
                : t("pages.composer.modeNlBody")}
            </p>
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
        </div>
      </Card>

      {mode === "workflow" ? (
        <WorkflowComposerSection
          autoMaterializationEnabled={autoMaterializationEnabled}
          capabilityHighlights={capabilityHighlights}
          fromRunId={fromRunId}
          onLaunchCreated={addRecentLaunch}
          preflightEnabled={preflightEnabled}
          recentLaunches={recentLaunches}
        />
      ) : (
        <NaturalLanguageComposerSection
          autoMaterializationEnabled={autoMaterializationEnabled}
          capabilityHighlights={capabilityHighlights}
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
