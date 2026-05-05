import { cn } from "@/shared/lib/utils";

type TemporalCursorMarkerProps = {
  position: number;
  className?: string;
};

export function TemporalCursorMarker({
  className,
  position,
}: TemporalCursorMarkerProps) {
  const clamped = Math.min(Math.max(position, 0), 1);
  return (
    <span
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute top-0 bottom-0 w-px bg-[var(--warning)]",
        className,
      )}
      data-testid="temporal-cursor-marker"
      style={{ left: `${clamped * 100}%` }}
    />
  );
}
