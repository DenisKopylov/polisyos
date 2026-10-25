import type { PropsWithChildren } from "react";
import { createContext, useContext } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useRunLiveUpdates } from "@/features/runs/live/useRunLiveUpdates";
import {
  type RunInspectorSummary,
  useRunDetailSummary,
} from "@/features/runs/routes/useRunDetailSummary";

export type { RunInspectorSummary } from "@/features/runs/routes/useRunDetailSummary";

const RunInspectorContext = createContext<RunInspectorSummary | null>(null);

export function RunInspectorProvider({
  children,
  runId,
}: PropsWithChildren<{ runId: string }>) {
  const { t } = useI18n();
  const summary = useRunDetailSummary(runId, t);
  const live = useRunLiveUpdates(summary.coreRunId);
  const currentSummary = {
    ...summary,
    liveTransport: live.isLiveConnected,
  };

  return (
    <RunInspectorContext.Provider value={currentSummary}>
      {children}
    </RunInspectorContext.Provider>
  );
}

export function useRunInspector() {
  const context = useContext(RunInspectorContext);
  if (!context) {
    throw new Error(
      "useRunInspector must be used within a RunInspectorProvider",
    );
  }
  return context;
}
