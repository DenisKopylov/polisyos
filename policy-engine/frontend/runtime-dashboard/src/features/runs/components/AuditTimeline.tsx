import { useMemo, useState } from "react";

import type {
  AuditTrailEntry,
  AuditTrailSeverity,
} from "@/features/runs/domain/compare";
import { Button, StatusTimeline } from "@/shared/ui";

type AuditTimelineProps = {
  entries: AuditTrailEntry[];
  emptyTitle: string;
  emptyBody: string;
};

const FILTERS: Array<{ key: "all" | AuditTrailSeverity; label: string }> = [
  { key: "all", label: "All" },
  { key: "fail", label: "Fail" },
  { key: "warn", label: "Warn" },
  { key: "info", label: "Info" },
];

function severityKind(severity: AuditTrailSeverity) {
  if (severity === "fail") {
    return "fail" as const;
  }
  if (severity === "warn") {
    return "warn" as const;
  }
  return "info" as const;
}

export function AuditTimeline({
  emptyBody,
  emptyTitle,
  entries,
}: AuditTimelineProps) {
  const [activeFilter, setActiveFilter] = useState<"all" | AuditTrailSeverity>(
    "all",
  );
  const visibleEntries = useMemo(
    () =>
      entries.filter(
        (entry) => activeFilter === "all" || entry.severity === activeFilter,
      ),
    [activeFilter, entries],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((filter) => (
          <Button
            key={filter.key}
            type="button"
            size="sm"
            variant={activeFilter === filter.key ? "primary" : "ghost"}
            onClick={() => setActiveFilter(filter.key)}
          >
            {filter.label}
          </Button>
        ))}
      </div>
      <StatusTimeline
        emptyBody={emptyBody}
        emptyTitle={emptyTitle}
        items={visibleEntries.map((entry) => ({
          id: entry.id,
          title: entry.title,
          body: entry.body,
          meta: <span className="text-muted text-xs">{entry.source}</span>,
          timestamp: entry.timestamp,
          tone: severityKind(entry.severity),
        }))}
      />
    </div>
  );
}
