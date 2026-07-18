import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "../lib/cn";

type NativeSelectProps = SelectHTMLAttributes<HTMLSelectElement>;

const Select = forwardRef<HTMLSelectElement, NativeSelectProps>(
  ({ className, children, ...props }, ref) => (
    <select ref={ref} className={cn("atlas-select", className)} {...props}>
      {children}
    </select>
  ),
);
Select.displayName = "Select";

export { Select };
