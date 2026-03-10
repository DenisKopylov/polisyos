import type { ReactNode } from "react";

import { Badge, EmptyState } from "@/shared/ui/primitives";
import { VirtualList, VIRTUALIZATION_THRESHOLD } from "@/shared/ui/VirtualList";

export type StatusTimelineTone = "fail" | "info" | "neutral" | "ok" | "warn";

export type StatusTimelineItem = {
  id: string;
  title: string;
  body?: ReactNode;
  timestamp?: ReactNode;
  tone?: StatusTimelineTone;
  meta?: ReactNode;
};

type StatusTimelineProps = {
  items: StatusTimelineItem[];
  emptyTitle: string;
  emptyBody: string;
};

function TimelineEntry({ item }: { item: StatusTimelineItem }) {
  return (
    <article className="rounded-2xl border border-line bg-surface/80 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className="mt-0.5 h-2.5 w-2.5 rounded-full bg-[var(--color-severity-low)]"
              style={{
                backgroundColor:
                  item.tone === "fail"
                    ? "var(--color-severity-high)"
                    : item.tone === "warn"
                      ? "var(--color-severity-medium)"
                      : item.tone === "ok"
                        ? "var(--color-status-approved)"
                        : item.tone === "info"
                          ? "var(--color-transport-live)"
                          : "var(--line)",
              }}
            />
            <p className="font-semibold">{item.title}</p>
          </div>
          {item.body ? <div className="text-sm text-muted">{item.body}</div> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {item.meta}
          {item.tone ? <Badge kind={item.tone}>{item.tone}</Badge> : null}
        </div>
      </div>
      {item.timestamp ? (
        <div className="mt-3 font-mono text-xs text-muted">{item.timestamp}</div>
      ) : null}
    </article>
  );
}

export function StatusTimeline({
  emptyBody,
  emptyTitle,
  items,
}: StatusTimelineProps) {
  if (items.length === 0) {
    return <EmptyState title={emptyTitle} body={emptyBody} />;
  }

  if (items.length < VIRTUALIZATION_THRESHOLD) {
    return (
      <div className="space-y-3">
        {items.map((item) => (
          <TimelineEntry key={item.id} item={item} />
        ))}
      </div>
    );
  }

  return (
    <VirtualList
      className="rounded-2xl"
      estimateSize={112}
      itemKey={(item) => item.id}
      items={items}
      maxHeight={520}
      renderItem={(item) => <TimelineEntry item={item} />}
    />
  );
}
