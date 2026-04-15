import { cn } from "@/lib/utils";
import { Card } from "@/shared/ui/primitives";

export type QuickInsight = {
  id: string;
  level: "info" | "success" | "warning" | "alert";
  title: string;
  body: string;
  metric?: { label: string; value: string };
  action?: { label: string; href: string };
};

type QuickInsightsPanelProps = {
  insights: QuickInsight[];
  title?: string;
  className?: string;
};

const LEVEL_CONFIG: Record<
  QuickInsight["level"],
  { icon: string; color: string }
> = {
  info: { icon: "\u2139", color: "var(--chart-secondary)" },
  success: { icon: "\u2713", color: "var(--chart-success)" },
  warning: { icon: "\u26A0", color: "var(--chart-warning)" },
  alert: { icon: "\u2717", color: "var(--chart-alert)" },
};

export function QuickInsightsPanel({
  insights,
  title = "Quick Insights",
  className,
}: QuickInsightsPanelProps) {
  if (insights.length === 0) {
    return (
      <Card className={cn("space-y-3", className)}>
        <h4 className="text-sm font-semibold">{title}</h4>
        <p className="text-muted text-sm">No insights available.</p>
      </Card>
    );
  }

  return (
    <Card className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">{title}</h4>
        <span className="text-muted text-xs">
          {insights.length} insight{insights.length !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="space-y-2">
        {insights.map((insight) => {
          const config = LEVEL_CONFIG[insight.level];
          return (
            <div
              key={insight.id}
              className="border-line flex gap-3 rounded-xl border p-3"
            >
              <span
                className="mt-0.5 shrink-0 text-sm"
                style={{ color: config.color }}
                aria-hidden
              >
                {config.icon}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">{insight.title}</p>
                <p className="text-muted mt-0.5 text-xs">{insight.body}</p>
                {insight.metric && (
                  <div className="mt-1.5 flex items-baseline gap-1.5">
                    <span className="text-muted text-xs">
                      {insight.metric.label}:
                    </span>
                    <span className="font-mono text-sm font-bold">
                      {insight.metric.value}
                    </span>
                  </div>
                )}
                {insight.action && (
                  <a
                    href={insight.action.href}
                    className="mt-1 inline-block text-xs font-medium text-[var(--chart-primary)] underline decoration-dotted underline-offset-2"
                  >
                    {insight.action.label}
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
