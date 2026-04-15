import { lazy, Suspense } from "react";

import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { PageSkeleton } from "@/shared/ui";

const RunsListPage = lazy(
  () => import("@/features/runs/routes/RunsListPage"),
);
const ClerkHistoryList = lazy(() =>
  import("@/features/clerk/components/ClerkHistoryList").then((m) => ({
    default: m.ClerkHistoryList,
  })),
);

export function ModeAwareRunsList() {
  const { isClerk } = useInterfaceMode();

  return (
    <Suspense fallback={<PageSkeleton />}>
      {isClerk ? <ClerkHistoryList /> : <RunsListPage />}
    </Suspense>
  );
}
