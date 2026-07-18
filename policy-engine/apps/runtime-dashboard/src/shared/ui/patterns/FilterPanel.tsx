import type { PropsWithChildren, ReactNode } from "react";

import { Card } from "@polisyos/atlas-ui";

type FilterPanelProps = PropsWithChildren<{
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}>;

export function FilterPanel({
  actions,
  children,
  description,
  title,
}: FilterPanelProps) {
  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">{title}</h3>
          {description ? (
            <div className="text-muted mt-1 text-sm">{description}</div>
          ) : null}
        </div>
        {actions}
      </div>
      {children}
    </Card>
  );
}
