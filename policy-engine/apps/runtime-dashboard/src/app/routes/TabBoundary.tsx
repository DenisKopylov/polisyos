import type { ReactNode } from "react";
import { Suspense } from "react";

import { PanelSkeleton } from "@/shared/ui";

export function TabBoundary({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PanelSkeleton rows={5} />}>{children}</Suspense>;
}
