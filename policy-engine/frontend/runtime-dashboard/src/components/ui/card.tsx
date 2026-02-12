import type { PropsWithChildren } from "react";

import { cn } from "../../lib/utils";

type CardProps = PropsWithChildren<{
  className?: string;
}>;

export function Card({ className, children }: CardProps) {
  return (
    <section className={cn("rounded-2xl border border-line bg-panel p-4 shadow-panel", className)}>
      {children}
    </section>
  );
}
