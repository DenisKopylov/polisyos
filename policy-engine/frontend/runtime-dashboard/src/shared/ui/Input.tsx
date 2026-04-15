import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type InputProps = InputHTMLAttributes<HTMLInputElement>;

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        "placeholder:text-muted-foreground/80 focus:border-accent/40 focus:ring-accent/20 border-input bg-popover text-foreground flex w-full rounded-2xl border px-4 py-3 text-sm shadow-xs transition outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
