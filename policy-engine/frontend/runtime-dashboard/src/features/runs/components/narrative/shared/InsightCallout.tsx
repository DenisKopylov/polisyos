import { cn } from "@/shared/lib/utils";

export type InsightLevel = "info" | "insight" | "warning" | "critical";

type InsightCalloutProps = {
  level?: InsightLevel;
  title?: string;
  children: React.ReactNode;
  className?: string;
};

const LEVEL_CONFIG: Record<
  InsightLevel,
  { icon: string; border: string; bg: string; text: string }
> = {
  info: {
    icon: "\u2139",
    border: "border-[var(--chart-secondary)]",
    bg: "bg-[var(--chart-secondary)]/5",
    text: "text-[var(--chart-secondary)]",
  },
  insight: {
    icon: "\u2605",
    border: "border-[var(--chart-success)]",
    bg: "bg-[var(--chart-success)]/5",
    text: "text-[var(--chart-success)]",
  },
  warning: {
    icon: "\u26A0",
    border: "border-[var(--chart-warning)]",
    bg: "bg-[var(--chart-warning)]/5",
    text: "text-[var(--chart-warning)]",
  },
  critical: {
    icon: "\u2717",
    border: "border-[var(--chart-alert)]",
    bg: "bg-[var(--chart-alert)]/5",
    text: "text-[var(--chart-alert)]",
  },
};

export function InsightCallout({
  level = "insight",
  title,
  children,
  className,
}: InsightCalloutProps) {
  const config = LEVEL_CONFIG[level];

  return (
    <div
      className={cn(
        "rounded-2xl border-s-4 p-4",
        config.border,
        config.bg,
        className,
      )}
      role="note"
    >
      <div className="flex items-start gap-3">
        <span className={cn("mt-0.5 text-lg", config.text)} aria-hidden>
          {config.icon}
        </span>
        <div className="min-w-0 flex-1">
          {title && (
            <p
              className={cn("text-sm font-semibold", config.text)}
              data-authored-exempt="true"
              data-authored-exempt-reason="Insight callout title is structural callout chrome; callout children carry authored prose where needed."
            >
              {title}
            </p>
          )}
          <div className="mt-0.5 text-sm">{children}</div>
        </div>
      </div>
    </div>
  );
}
