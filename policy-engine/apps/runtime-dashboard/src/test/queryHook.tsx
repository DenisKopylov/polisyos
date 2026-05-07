import type { PropsWithChildren } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { AlertDialogProvider } from "@/app/providers/AlertDialogProvider";
import { TelemetryProvider } from "@/app/providers/TelemetryProvider";
import { ToastProvider } from "@/app/providers/ToastProvider";
import {
  HighContrastProvider,
  LiveAnnouncerProvider,
  ReducedMotionProvider,
} from "@/shared/a11y";
import { createTestQueryClient } from "@/test/queryClient";

export function createQueryHookHarness() {
  const queryClient = createTestQueryClient();

  function QueryHookWrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <TelemetryProvider>
          <HighContrastProvider>
            <ReducedMotionProvider>
              <LiveAnnouncerProvider>
                <ToastProvider>
                  <AlertDialogProvider>{children}</AlertDialogProvider>
                </ToastProvider>
              </LiveAnnouncerProvider>
            </ReducedMotionProvider>
          </HighContrastProvider>
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
