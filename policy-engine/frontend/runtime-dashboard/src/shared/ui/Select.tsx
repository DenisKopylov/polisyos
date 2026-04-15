import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type NativeSelectProps = SelectHTMLAttributes<HTMLSelectElement>;

const Select = forwardRef<HTMLSelectElement, NativeSelectProps>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "focus:border-accent/40 focus:ring-accent/20 border-input bg-popover text-foreground w-full rounded-2xl border px-4 py-3 text-sm shadow-xs transition outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);
Select.displayName = "Select";

export { Select };
