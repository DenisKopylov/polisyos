import type { PropsWithChildren } from "react";
import { matchPath, useLocation } from "react-router-dom";

import { useRunScenarios } from "@/api/hooks/useScenarioCapabilities";
import { AppMobileNav } from "@/app/layout/AppMobileNav";
import { GlobalRuntimeBanner } from "@/app/layout/GlobalRuntimeBanner";
import type { CounterfactualMode } from "@/app/providers/scenario-scope";
import { useMaybeCounterfactual } from "@/app/providers/useCounterfactual";
import { CommandPalette } from "@/features/commandPalette";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useIsMobile } from "@/shared/ui/responsive";
import { CounterfactualModeSwitch } from "@/shared/ui/counterfactual/CounterfactualModeSwitch";
import { ScenarioPicker } from "@/shared/ui/counterfactual/ScenarioPicker";
import { TemporalScrubber } from "@/shared/ui/temporal";
import { TrustInspector } from "@/shared/ui/trust-view";
import Header from "@/app/layout/Header";
import Sidebar from "@/app/layout/Sidebar";

function resolveRunId(pathname: string) {
  const detailMatch =
    matchPath({ path: "/runs/:runId/*", end: false }, pathname) ??
    matchPath({ path: "/runs/:runId", end: true }, pathname);
  const runId = detailMatch?.params.runId ?? null;
  return runId && runId !== "compare" ? runId : null;
}

function CounterfactualShellRail({ runId }: { runId: string }) {
  const { t } = useI18n();
  const counterfactual = useMaybeCounterfactual();
  const scenariosQuery = useRunScenarios(runId);
  const scenarios = scenariosQuery.data?.scenarios ?? [];
  const firstScenarioId = scenarios[0]?.id ?? null;
  const disabledReason = scenariosQuery.isLoading
    ? t("shared.ui.counterfactual.loadingScenarios")
    : scenariosQuery.isError
      ? t("shared.ui.counterfactual.scenarioLoadError")
      : scenarios.length === 0
        ? t("shared.ui.counterfactual.noScenarioSupport")
        : null;

  const handleModeChange = (mode: CounterfactualMode) => {
    if (!counterfactual) {
      return;
    }
    if (mode !== "actual" && !counterfactual.scenarioId && firstScenarioId) {
      counterfactual.setScenarioId(firstScenarioId);
    }
    counterfactual.setMode(mode);
  };

  return (
    <div
      className="border-border bg-background/80 mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border px-3 py-2"
      data-testid="counterfactual-shell-rail"
    >
      <CounterfactualModeSwitch
        disabled={scenariosQuery.isLoading || scenarios.length === 0}
        value={counterfactual?.mode ?? "actual"}
        onChange={handleModeChange}
      />
      <ScenarioPicker
        className="min-w-[16rem] flex-1 sm:flex-none"
        disabledReason={disabledReason}
        scenarios={scenarios}
      />
    </div>
  );
}

export default function AppShell({ children }: PropsWithChildren) {
  const { t } = useI18n();
  const isMobile = useIsMobile();
  const location = useLocation();
  const runId = resolveRunId(location.pathname);

  return (
    <div className="atlas-shell-frame" data-testid="app-shell">
      <CommandPalette />
      <TrustInspector />
      <a
        href="#main-content"
        className="border-line bg-panel text-text sr-only top-4 left-4 z-50 rounded-full border px-4 py-2 text-sm font-semibold focus:not-sr-only focus:absolute"
      >
        {t("common.skipToContent")}
      </a>
      <div className="atlas-shell">
        <div className="app-shell">
          <Sidebar />
          <div className="surface">
            <GlobalRuntimeBanner />
            <Header />
            <TemporalScrubber className={runId ? "mb-2" : "mb-4"} />
            {runId ? <CounterfactualShellRail runId={runId} /> : null}
            <main id="main-content" className="shell-main" tabIndex={-1}>
              {children}
            </main>
          </div>
        </div>
      </div>
      {isMobile && <AppMobileNav />}
    </div>
  );
}
