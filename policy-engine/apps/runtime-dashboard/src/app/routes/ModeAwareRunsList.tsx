import { lazy, Suspense } from "react";

import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { PageSkeleton } from "@polisyos/atlas-ui";

const RunsListPage = lazy(() =>
  import("@/features/runs/routes.public").then((module) => ({
    default: module.RunsListPage,
  })),
);
const ClerkHistoryList = lazy(() =>
  import("@/features/clerk/routes.public").then((module) => ({
    default: module.ClerkHistoryList,
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
