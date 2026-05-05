import { forwardRef, type TextareaHTMLAttributes } from "react";

import { cn } from "@/shared/lib/utils";

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn("atlas-textarea", className)}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export { Textarea };
