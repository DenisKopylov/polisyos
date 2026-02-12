import { cn } from "../../lib/utils";

type StatusKind = "ok" | "fail" | "warn" | "unknown";

type StatusBadgeProps = {
  label: string;
  kind?: StatusKind;
};

const badgeStyle: Record<StatusKind, string> = {
  ok: "bg-success/10 text-success border-success/30",
  fail: "bg-danger/10 text-danger border-danger/30",
  warn: "bg-warning/10 text-warning border-warning/30",
  unknown: "bg-muted/15 text-muted border-line",
};

export default function StatusBadge({ label, kind = "unknown" }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide",
        badgeStyle[kind],
      )}
    >
      {label}
    </span>
  );
}
