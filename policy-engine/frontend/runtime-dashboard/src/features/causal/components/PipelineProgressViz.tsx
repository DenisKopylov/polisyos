import { useMemo } from "react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Card } from "@/shared/ui/primitives";
import { AnimatedProgress } from "@/shared/charts";

import type { PipelineStage, PipelineStageStatus } from "../types";

type PipelineProgressVizProps = {
  stages: PipelineStage[];
  title?: string;
  className?: string;
};

const STATUS_CONFIG: Record<
  PipelineStageStatus,
  { color: string; icon: string; bgClass: string }
> = {
  pending: {
    color: "var(--chart-neutral)",
    icon: "\u25CB",
    bgClass: "bg-[var(--chart-neutral)]/10",
  },
  running: {
    color: "var(--chart-secondary)",
    icon: "\u25D4",
    bgClass: "bg-[var(--chart-secondary)]/10",
  },
  completed: {
    color: "var(--chart-success)",
    icon: "\u2713",
    bgClass: "bg-[var(--chart-success)]/10",
  },
  failed: {
    color: "var(--chart-alert)",
    icon: "\u2717",
    bgClass: "bg-[var(--chart-alert)]/10",
  },
  skipped: {
    color: "var(--chart-neutral)",
    icon: "\u2014",
    bgClass: "bg-[var(--chart-neutral)]/5",
  },
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60_000).toFixed(1)}m`;
}

export function PipelineProgressViz({
  stages,
  title,
  className,
}: PipelineProgressVizProps) {
  const { t } = useI18n();
  const resolvedTitle = title ?? t("causal.pipeline.title");
  // Compute depth for each stage (BFS from roots)
  const depthMap = useMemo(() => {
    const deps = new Map(stages.map((s) => [s.id, s.dependsOn]));
    const depth = new Map<string, number>();
    const queue: string[] = [];

    for (const s of stages) {
      if (s.dependsOn.length === 0) {
        depth.set(s.id, 0);
        queue.push(s.id);
      }
    }

    let head = 0;
    while (head < queue.length) {
      const current = queue[head++];
      const d = depth.get(current) ?? 0;
      for (const s of stages) {
        if (s.dependsOn.includes(current)) {
          const existing = depth.get(s.id);
          if (existing === undefined || existing < d + 1) {
            depth.set(s.id, d + 1);
            if (existing === undefined) queue.push(s.id);
          }
        }
      }
    }

    // Fallback for disconnected stages
    for (const s of stages) {
      if (!depth.has(s.id)) depth.set(s.id, 0);
    }
    return depth;
  }, [stages]);

  const completedCount = stages.filter((s) => s.status === "completed").length;
  const failedCount = stages.filter((s) => s.status === "failed").length;
  const progressPct =
    stages.length > 0 ? Math.round((completedCount / stages.length) * 100) : 0;

  const totalDuration = stages.reduce((sum, s) => sum + (s.durationMs ?? 0), 0);

  // Group by depth
  const columns = useMemo(() => {
    const cols = new Map<number, PipelineStage[]>();
    for (const s of stages) {
      const d = depthMap.get(s.id) ?? 0;
      const col = cols.get(d) ?? [];
      col.push(s);
      cols.set(d, col);
    }
    return Array.from(cols.entries()).sort(([a], [b]) => a - b);
  }, [stages, depthMap]);

  return (
    <Card className={cn("space-y-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">{resolvedTitle}</h3>
        <div className="flex items-center gap-3 text-xs">
          {failedCount > 0 && (
            <span className="font-semibold text-[var(--chart-alert)]">
              {t("causal.pipeline.failedCount", { count: failedCount })}
            </span>
          )}
          <span className="text-muted">
            {t("causal.pipeline.stageProgress", {
              completed: completedCount,
              total: stages.length,
            })}
          </span>
          {totalDuration > 0 && (
            <span className="text-muted">{formatDuration(totalDuration)}</span>
          )}
        </div>
      </div>

      <AnimatedProgress
        value={progressPct}
        height={6}
        colorByConfidence
        label={resolvedTitle}
      />

      {/* DAG visualization */}
      <div className="flex gap-2 overflow-x-auto py-2">
        {columns.map(([depth, col]) => (
          <div key={depth} className="flex shrink-0 flex-col gap-2">
            {col.map((stage) => {
              const config = STATUS_CONFIG[stage.status];
              return (
                <div
                  key={stage.id}
                  className={cn(
                    "border-line w-44 rounded-xl border p-3 transition-colors",
                    config.bgClass,
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="text-sm"
                      style={{ color: config.color }}
                      aria-hidden="true"
                    >
                      {config.icon}
                    </span>
                    <span className="truncate text-sm font-semibold">
                      {stage.label}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-xs">
                    <span
                      className="capitalize"
                      style={{ color: config.color }}
                    >
                      {stage.status}
                    </span>
                    {stage.durationMs != null && (
                      <span className="text-muted">
                        {formatDuration(stage.durationMs)}
                      </span>
                    )}
                  </div>
                  {stage.detail && (
                    <p className="text-muted mt-1 truncate text-xs">
                      {stage.detail}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Dependency arrows (connector lines between columns) */}
      {columns.length > 1 && (
        <div className="text-muted flex items-center gap-1 text-xs">
          <span>{"\u2192"}</span>
          <span>{t("causal.pipeline.flowHint")}</span>
        </div>
      )}
    </Card>
  );
}
