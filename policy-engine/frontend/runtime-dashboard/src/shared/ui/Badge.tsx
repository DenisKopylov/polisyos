import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

export type BadgeKind = "ok" | "warn" | "fail" | "neutral" | "info";

type BadgeProps = {
  kind?: BadgeKind;
  className?: string;
  children: ReactNode;
} & HTMLAttributes<HTMLSpanElement>;

const badgeClassName: Record<BadgeKind, string> = {
  ok: "bg-[color-mix(in_srgb,var(--color-status-approved)_14%,transparent)] text-[var(--color-status-approved)]",
  warn: "bg-[color-mix(in_srgb,var(--color-status-pending)_16%,transparent)] text-[var(--color-status-pending)]",
  fail: "bg-[color-mix(in_srgb,var(--color-status-rejected)_14%,transparent)] text-[var(--color-status-rejected)]",
  neutral: "bg-white/65 text-muted",
  info: "bg-[color-mix(in_srgb,var(--color-transport-live)_14%,transparent)] text-[var(--color-transport-live)]",
};

export function Badge({
  children,
  className,
  kind = "neutral",
  ...rest
}: BadgeProps) {
  return (
    <span
      {...rest}
      className={cn(
        "inline-flex items-center justify-center rounded-[var(--radius-pill)] px-3 py-2 text-xs font-extrabold uppercase tracking-[0.05em]",
        badgeClassName[kind],
        className,
      )}
    >
      {children}
    </span>
  );
}
