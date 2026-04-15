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
import { cn } from "@/lib/utils";
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

  function addRecentLaunch(runId: string, status: string) {
    setRecentLaunches((previous) =>
      [{ runId, status }, ...previous].slice(0, 5),
    );
  }

  return (
    <div className="space-y-5" data-testid="composer-page">
      <h1 className="sr-only">{t("pages.composer.title")}</h1>

      <div className="border-line bg-panel grid gap-3 rounded-3xl border p-3 md:grid-cols-5">
        {(["workflow", "nl", "evidence", "guardrails", "launch"] as const).map(
          (step, index) => {
            const isActive =
              step === "workflow"
                ? mode === "workflow"
                : step === "nl"
                  ? mode === "nl"
                  : true;
            const labelKey = `pages.composer.steps.${step}`;
            return (
              <button
                key={step}
                type="button"
                onClick={
                  step === "workflow" || step === "nl"
                    ? () => setMode(step)
                    : undefined
                }
                disabled={step !== "workflow" && step !== "nl"}
                data-testid={
                  step === "workflow"
                    ? "composer-mode-workflow"
                    : step === "nl"
                      ? "composer-mode-nl"
                      : undefined
                }
                className={cn(
                  "rounded-2xl border px-3 py-4 text-left",
                  isActive
                    ? "border-accent/35 bg-accent/10"
                    : "bg-surface/75 border-line",
                  step !== "workflow" && step !== "nl"
                    ? "cursor-default opacity-75"
                    : "",
                )}
              >
                <span className="text-muted block text-xs tracking-wide uppercase">
                  {index + 1}
                </span>
                <strong className="mt-2 block text-sm">{t(labelKey)}</strong>
              </button>
            );
          },
        )}
      </div>

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
