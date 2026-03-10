import type { SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export function Select({ className, children, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        "focus:border-accent/40 focus:ring-accent/20 w-full rounded-2xl border border-line bg-panelStrong px-4 py-3 text-sm text-text shadow-sm outline-none transition focus:ring-2",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}
