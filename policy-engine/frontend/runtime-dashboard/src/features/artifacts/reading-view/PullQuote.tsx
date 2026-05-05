import type { BlockquoteHTMLAttributes } from "react";

import { cn } from "@/shared/lib/utils";
import { AuthoredText } from "@/shared/ui/authored-text";

type PullQuoteProps = {
  attribution?: string;
  className?: string;
} & BlockquoteHTMLAttributes<HTMLQuoteElement>;

export function PullQuote({
  attribution,
  children,
  className,
  ...rest
}: PullQuoteProps) {
  if (!children) {
    return null;
  }

  return (
    <blockquote {...rest} className={cn("reading-pull-quote", className)}>
      <AuthoredText as="p" author="human">
        {children}
      </AuthoredText>
      {attribution ? (
        <footer className="text-muted mt-3 text-xs tracking-[0.18em] uppercase not-italic">
          {attribution}
        </footer>
      ) : null}
    </blockquote>
  );
}
