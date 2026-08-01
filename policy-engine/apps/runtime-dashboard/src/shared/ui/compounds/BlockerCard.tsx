import type { PolicyDesignCaseProjectionBlocker } from "@polisyos/runtime-api-client";

import { cn } from "@/shared/lib/utils";

import { NegativeCertificateCard } from "./NegativeCertificateCard";

export type BlockerCardProps = {
  blocker: PolicyDesignCaseProjectionBlocker;
  className?: string;
};

/** Renders one producer-owned projection blocker without a local severity input. */
export function BlockerCard({ blocker, className }: BlockerCardProps) {
  return (
    <section
      aria-label={`Blocker: ${blocker.code}`}
      className={cn(
        "border-l-2 border-[var(--color-status-rejected)]",
        className,
      )}
      data-producer-blocker-code={blocker.code}
      data-producer-blocker-severity={blocker.severity}
      data-testid="blocker-card"
    >
      <NegativeCertificateCard blocker={blocker} />
    </section>
  );
}
