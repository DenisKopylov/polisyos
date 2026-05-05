import type { ReactNode } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
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
  const { t } = useI18n();
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
              className="border-line bg-surface/70 rounded-2xl border p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold">{item.label}</p>
                  <p className="text-muted mt-1 font-mono text-xs">
                    {item.artifactId}
                  </p>
                  {item.meta ? (
                    <div className="text-muted mt-2 text-sm">{item.meta}</div>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {item.badge}
                  {item.href ? (
                    <Button href={item.href} size="sm" variant="ghost">
                      {t("common.open")}
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
