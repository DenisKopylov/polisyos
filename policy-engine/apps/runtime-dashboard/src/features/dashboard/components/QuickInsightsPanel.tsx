import { useI18n } from "@/shared/i18n/LocaleProvider";
import type { InteractionState } from "@/shared/lib/domain/statusOwnership";
import { cn } from "@/shared/lib/utils";
import { Card } from "@polisyos/atlas-ui";

export type QuickInsight = {
  id: string;
  level: InteractionState;
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

export function QuickInsightsPanel({
  insights,
  title = "Quick Insights",
  className,
}: QuickInsightsPanelProps) {
  const { t } = useI18n();
  if (insights.length === 0) {
    return (
      <Card className={cn("space-y-3", className)}>
        <h4 className="text-sm font-semibold">{title}</h4>
        <p className="text-muted text-sm">
          {t("features.dashboard.quickInsights.empty")}
        </p>
      </Card>
    );
  }

  return (
    <Card className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">{title}</h4>
        <span className="text-muted text-xs">
          {t("features.dashboard.quickInsights.count", {
            count: insights.length,
          })}
        </span>
      </div>

      <div className="space-y-2">
        {insights.map((insight) => (
          <article
            key={insight.id}
            className="border-line flex gap-3 rounded-xl border p-3"
            data-interaction-purpose={insight.level.authorityPurpose}
          >
            <span className="text-muted mt-0.5 shrink-0 text-sm" aria-hidden>
              {"\u2022"}
            </span>
            <div className="min-w-0 flex-1">
              <span className="text-muted text-xs">{insight.level.label}</span>
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
          </article>
        ))}
      </div>
    </Card>
  );
}
