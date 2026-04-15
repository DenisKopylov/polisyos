import { lazy, Suspense } from "react";

import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { PageSkeleton } from "@/shared/ui";

const RunDetailLayout = lazy(
  () => import("@/features/runs/routes/RunDetailLayout"),
);
const ClerkRunSummaryPage = lazy(
  () => import("@/features/clerk/routes/ClerkRunSummaryPage"),
);

export function ModeAwareRunDetail() {
  const { isClerk } = useInterfaceMode();

  return (
    <Suspense fallback={<PageSkeleton />}>
      {isClerk ? <ClerkRunSummaryPage /> : <RunDetailLayout />}
    </Suspense>
  );
}
