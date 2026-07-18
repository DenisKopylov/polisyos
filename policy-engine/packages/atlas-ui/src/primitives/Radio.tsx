import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "../lib/cn";

type RadioProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type">;

const Radio = forwardRef<HTMLInputElement, RadioProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      type="radio"
      className={cn("atlas-radio", className)}
      {...props}
    />
  ),
);
Radio.displayName = "Radio";

export { Radio };
