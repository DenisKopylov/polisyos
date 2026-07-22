import { useMemo, useState } from "react";

import type {
  AuditTrailEntry,
  AuditTrailSource,
} from "@/features/runs/domain/compare";
import { Button } from "@polisyos/atlas-ui";
import { StatusTimeline } from "@/shared/ui";

type AuditTimelineProps = {
  entries: AuditTrailEntry[];
  emptyTitle: string;
  emptyBody: string;
};

const FILTERS: Array<{ key: "all" | AuditTrailSource; label: string }> = [
  { key: "all", label: "All" },
  { key: "governance", label: "Governance" },
  { key: "runtime", label: "Runtime" },
  { key: "timeline", label: "Timeline" },
];

export function AuditTimeline({
  emptyBody,
  emptyTitle,
  entries,
}: AuditTimelineProps) {
  const [activeFilter, setActiveFilter] = useState<"all" | AuditTrailSource>(
    "all",
  );
  const visibleEntries = useMemo(
    () =>
      entries.filter(
        (entry) => activeFilter === "all" || entry.source === activeFilter,
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
          meta: (
            <span className="text-muted text-xs">
              {entry.source}
              {entry.ownerLabel ? ` · ${entry.ownerLabel}` : ""}
            </span>
          ),
          timestamp: entry.timestamp,
          recordedState: entry.recordedState,
        }))}
      />
    </div>
  );
}
