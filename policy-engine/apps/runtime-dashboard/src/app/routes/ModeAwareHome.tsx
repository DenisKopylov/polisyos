import { lazy, Suspense } from "react";

import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { PageSkeleton } from "@polisyos/atlas-ui";

const DashboardPage = lazy(() =>
  import("@/features/dashboard/routes.public").then((module) => ({
    default: module.DashboardPage,
  })),
);
const ClerkChatPage = lazy(() =>
  import("@/features/clerk/routes.public").then((module) => ({
    default: module.ClerkChatPage,
  })),
);

export function ModeAwareHome() {
  const { isClerk } = useInterfaceMode();

  return (
    <Suspense fallback={<PageSkeleton />}>
      {isClerk ? <ClerkChatPage /> : <DashboardPage />}
    </Suspense>
  );
}
