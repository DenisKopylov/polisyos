import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        "placeholder:text-muted/80 focus:border-accent/40 focus:ring-accent/20 w-full rounded-2xl border border-line bg-panelStrong px-4 py-3 text-sm text-text shadow-sm outline-none transition focus:ring-2",
        className,
      )}
      {...props}
    />
  );
}
