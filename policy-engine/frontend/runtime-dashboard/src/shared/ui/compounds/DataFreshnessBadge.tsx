import { Badge } from "@/shared/ui/primitives";

type DataFreshnessBadgeProps = {
  generatedAt?: string | null;
  staleAfterMs?: number;
};

function formatRelativeAge(date: Date) {
  const diffMs = Date.now() - date.getTime();
  const diffSeconds = Math.round(diffMs / 1000);
  const formatter = new Intl.RelativeTimeFormat(undefined, {
    numeric: "auto",
  });

  if (Math.abs(diffSeconds) < 60) {
    return formatter.format(-diffSeconds, "second");
  }

  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 60) {
    return formatter.format(-diffMinutes, "minute");
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) {
    return formatter.format(-diffHours, "hour");
  }

  const diffDays = Math.round(diffHours / 24);
  return formatter.format(-diffDays, "day");
}

export function DataFreshnessBadge({
  generatedAt,
  staleAfterMs = 5 * 60_000,
}: DataFreshnessBadgeProps) {
  if (!generatedAt) {
    return <Badge kind="warn">No freshness metadata</Badge>;
  }

  const date = new Date(generatedAt);
  if (Number.isNaN(date.getTime())) {
    return <Badge kind="warn">Unknown freshness</Badge>;
  }

  const ageMs = Date.now() - date.getTime();
  return (
    <Badge
      kind={ageMs > staleAfterMs ? "warn" : "ok"}
      className="tracking-normal normal-case"
      title={date.toLocaleString()}
    >
      Updated {formatRelativeAge(date)}
    </Badge>
  );
}
