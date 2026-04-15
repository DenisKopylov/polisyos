import { lazy, Suspense } from "react";

import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { PageSkeleton } from "@/shared/ui";

const DashboardPage = lazy(
  () => import("@/features/dashboard/routes/DashboardPage"),
);
const ClerkChatPage = lazy(
  () => import("@/features/clerk/routes/ClerkChatPage"),
);

export function ModeAwareHome() {
  const { isClerk } = useInterfaceMode();

  return (
    <Suspense fallback={<PageSkeleton />}>
      {isClerk ? <ClerkChatPage /> : <DashboardPage />}
    </Suspense>
  );
}
