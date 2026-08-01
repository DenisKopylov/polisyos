import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";

type FrequencyDotsProps = {
  total?: number;
  highlighted: number;
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
};

const SIZE_MAP = {
  sm: { dot: 6, gap: 2, cols: 20 },
  md: { dot: 8, gap: 3, cols: 10 },
  lg: { dot: 10, gap: 4, cols: 10 },
} as const;

export function FrequencyDots({
  total = 100,
  highlighted,
  label,
  size = "md",
  className,
}: FrequencyDotsProps) {
  const { t } = useI18n();
  const clamped = Math.max(0, Math.min(total, Math.round(highlighted)));
  const dims = SIZE_MAP[size];
  const rows = Math.ceil(total / dims.cols);

  const pct = Math.round((clamped / total) * 100);
  const ariaLabel = `${clamped} out of ${total} (${pct}%)${label ? `. ${label}` : ""}`;

  return (
    <div
      className={cn("inline-flex flex-col gap-2", className)}
      role="img"
      aria-label={ariaLabel}
    >
      <div
        className="grid"
        style={{
          gridTemplateColumns: `repeat(${dims.cols}, ${dims.dot}px)`,
          gap: dims.gap,
        }}
      >
        {Array.from({ length: total }, (_, i) => (
          <div
            key={i}
            className="rounded-full"
            data-testid="frequency-dot"
            style={{
              width: dims.dot,
              height: dims.dot,
              backgroundColor:
                i < clamped ? "var(--chart-primary)" : "var(--line)",
              opacity: i < clamped ? 1 : 0.4,
            }}
          />
        ))}
      </div>
      {label && (
        <p className="text-muted-foreground text-xs">
          <span className="text-foreground font-semibold">{clamped}</span>{" "}
          {t("shared.charts.frequencyDots.outOf", { total })} — {label}
        </p>
      )}
    </div>
  );
}
