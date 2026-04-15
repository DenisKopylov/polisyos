import type { PropsWithChildren } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { queryClient } from "../../api/queryClient";
import { AuthSessionProvider } from "../../app/auth/AuthSessionProvider";
import { AuthzProvider } from "../../app/authz/AuthzProvider";
import { AlertDialogProvider } from "../../app/providers/AlertDialogProvider";
import { FeatureFlagProvider } from "../../app/providers/FeatureFlagProvider";
import { InterfaceModeProvider } from "../../app/providers/InterfaceModeProvider";
import { LiveAnnouncerProvider } from "../../app/providers/LiveAnnouncerProvider";
import { OfflineQueueProvider } from "../../app/providers/OfflineQueueProvider";
import { TelemetryProvider } from "../../app/providers/TelemetryProvider";
import { DensityProvider } from "../../app/providers/DensityProvider";
import { ThemeProvider } from "../../app/providers/ThemeProvider";
import { ToastProvider } from "../../app/providers/ToastProvider";
import { LocaleProvider } from "../../i18n/LocaleProvider";
import { NetworkStatusProvider } from "@/shared/network";

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <LocaleProvider>
        <TelemetryProvider>
          <LiveAnnouncerProvider>
            <ToastProvider>
              <AlertDialogProvider>
                <AuthSessionProvider>
                  <AuthzProvider>
                    <NetworkStatusProvider>
                      <OfflineQueueProvider>
                        <FeatureFlagProvider>
                          <InterfaceModeProvider>
                            <DensityProvider>
                              <ThemeProvider>{children}</ThemeProvider>
                            </DensityProvider>
                          </InterfaceModeProvider>
                        </FeatureFlagProvider>
                      </OfflineQueueProvider>
                    </NetworkStatusProvider>
                  </AuthzProvider>
                </AuthSessionProvider>
              </AlertDialogProvider>
            </ToastProvider>
          </LiveAnnouncerProvider>
        </TelemetryProvider>
      </LocaleProvider>
    </QueryClientProvider>
  );
}
