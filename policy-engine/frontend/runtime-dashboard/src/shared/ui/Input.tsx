import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        "placeholder:text-muted/80 focus:border-accent/40 focus:ring-accent/20 border-line bg-panelStrong text-text w-full rounded-2xl border px-4 py-3 text-sm shadow-sm transition outline-none focus:ring-2",
        className,
      )}
      {...props}
    />
  );
}
