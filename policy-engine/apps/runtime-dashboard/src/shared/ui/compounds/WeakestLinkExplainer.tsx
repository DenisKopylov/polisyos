import type { ReactNode } from "react";
import type { DepthNDomainRunProjection } from "@polisyos/runtime-api-client";
import { Badge, Card } from "@polisyos/atlas-ui";

import { cn } from "@/shared/lib/utils";

const NO_WEAKEST_LINK_LABEL = "No weakest link supplied";

export type WeakestLinkExplainerProps = {
  className?: string;
  projection: DepthNDomainRunProjection;
  title?: ReactNode;
};

/** Displays the producer-supplied weakest links in their original order. */
export function WeakestLinkExplainer({
  className,
  projection,
  title = "Weakest grounded boundary",
}: WeakestLinkExplainerProps) {
  return (
    <Card
      className={cn("space-y-3", className)}
      data-weakest-link-source="producer"
      data-testid="weakest-link-explainer"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-lg font-semibold">{title}</h3>
        <Badge kind="neutral">{projection.domain_role}</Badge>
      </div>

      {projection.weakest_links.length > 0 ? (
        <ol className="space-y-2">
          {projection.weakest_links.map((weakestLink, index) => (
            <li
              className="border-line bg-surface/70 rounded-2xl border p-3 text-sm"
              key={`${index}:${weakestLink}`}
            >
              {weakestLink}
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-muted text-sm">{NO_WEAKEST_LINK_LABEL}</p>
      )}
    </Card>
  );
}
