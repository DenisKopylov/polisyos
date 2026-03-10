import type { PropsWithChildren } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { AlertDialogProvider } from "@/app/providers/AlertDialogProvider";
import { LiveAnnouncerProvider } from "@/app/providers/LiveAnnouncerProvider";
import { TelemetryProvider } from "@/app/providers/TelemetryProvider";
import { ToastProvider } from "@/app/providers/ToastProvider";
import { createTestQueryClient } from "@/test/queryClient";

export function createQueryHookHarness() {
  const queryClient = createTestQueryClient();

  function QueryHookWrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <TelemetryProvider>
          <LiveAnnouncerProvider>
            <ToastProvider>
              <AlertDialogProvider>{children}</AlertDialogProvider>
            </ToastProvider>
          </LiveAnnouncerProvider>
        </TelemetryProvider>
      </QueryClientProvider>
    );
  }

  return {
    queryClient,
    wrapper: QueryHookWrapper,
  };
}

export function createQueryHookWrapper() {
  return createQueryHookHarness().wrapper;
}
