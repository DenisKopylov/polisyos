import type { ReactNode } from "react";

import { Button, Card, EmptyState } from "@/shared/ui/primitives";

export type EvidenceChainItem = {
  artifactId: string;
  label: string;
  meta?: ReactNode;
  href?: string;
  badge?: ReactNode;
};

type EvidenceChainProps = {
  title: string;
  items: EvidenceChainItem[];
  emptyTitle: string;
  emptyBody: string;
};

export function EvidenceChain({
  emptyBody,
  emptyTitle,
  items,
  title,
}: EvidenceChainProps) {
  return (
    <Card className="space-y-3">
      <h3 className="text-lg font-semibold">{title}</h3>
      {items.length === 0 ? (
        <EmptyState title={emptyTitle} body={emptyBody} />
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <article
              key={item.artifactId}
              className="rounded-2xl border border-line bg-surface/70 p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold">{item.label}</p>
                  <p className="mt-1 font-mono text-xs text-muted">
                    {item.artifactId}
                  </p>
                  {item.meta ? (
                    <div className="mt-2 text-sm text-muted">{item.meta}</div>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {item.badge}
                  {item.href ? (
                    <Button href={item.href} size="sm" variant="ghost">
                      Open
                    </Button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </Card>
  );
}
