import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type DetailLayoutProps = {
  header?: ReactNode;
  sidebar?: ReactNode;
  content: ReactNode;
  footer?: ReactNode;
  className?: string;
};

export function DetailLayout({
  className,
  content,
  footer,
  header,
  sidebar,
}: DetailLayoutProps) {
  return (
    <div className={cn("space-y-5", className)}>
      {header}
      <div
        className={cn(
          "grid gap-5",
          sidebar ? "xl:grid-cols-[280px,1fr]" : "grid-cols-1",
        )}
      >
        {sidebar ? <div>{sidebar}</div> : null}
        <div>{content}</div>
      </div>
      {footer}
    </div>
  );
}
