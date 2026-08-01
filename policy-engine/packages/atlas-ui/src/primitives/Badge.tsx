import type { HTMLAttributes, ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../lib/cn";

export const badgeVariants = cva(
  "inline-flex items-center justify-center rounded-[var(--radius-pill)] px-3 py-2 text-xs font-extrabold tracking-[0.05em] uppercase transition-colors",
  {
    variants: {
      kind: {
        ok: "bg-[color-mix(in_srgb,var(--color-status-approved)_14%,transparent)] text-[var(--color-status-approved)]",
        warn: "bg-[color-mix(in_srgb,var(--color-status-pending)_16%,transparent)] text-[var(--color-status-pending)]",
        fail: "bg-[color-mix(in_srgb,var(--color-status-rejected)_14%,transparent)] text-[var(--color-status-rejected)]",
        neutral: "bg-white/65 text-muted",
        info: "bg-[color-mix(in_srgb,var(--color-transport-live)_14%,transparent)] text-[var(--color-transport-live)]",
        outline: "border border-border text-foreground",
      },
    },
    defaultVariants: { kind: "neutral" },
  },
);

/** Presentation-only tone. It carries no runtime status or authority semantics. */
export type BadgeTone = NonNullable<VariantProps<typeof badgeVariants>["kind"]>;

export type BadgeProps = VariantProps<typeof badgeVariants> & {
  className?: string;
  children: ReactNode;
} & HTMLAttributes<HTMLSpanElement>;

export function Badge({
  children,
  className,
  kind = "neutral",
  ...rest
}: BadgeProps) {
  return (
    <span {...rest} className={cn(badgeVariants({ kind }), className)}>
      {children}
    </span>
  );
}
