import { startTransition, type PropsWithChildren } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { queryClient } from "../../api/queryClient";
import { AuthSessionProvider } from "../../app/auth/AuthSessionProvider";
import { AuthzProvider } from "../../app/authz/AuthzProvider";
import { AlertDialogProvider } from "../../app/providers/AlertDialogProvider";
import { FeatureFlagProvider } from "../../app/providers/FeatureFlagProvider";
import { InterfaceModeProvider } from "../../app/providers/InterfaceModeProvider";
import { OfflineQueueProvider } from "../../app/providers/OfflineQueueProvider";
import { TelemetryProvider } from "../../app/providers/TelemetryProvider";
import { CounterfactualProvider } from "../../app/providers/CounterfactualProvider";
import { TemporalCursorProvider } from "../../app/providers/TemporalCursorProvider";
import { TrustViewProvider } from "../../app/providers/TrustViewProvider";
import { QuantityRuntimeProvider } from "../../app/providers/QuantityRuntimeProvider";
import { DensityProvider } from "../../app/providers/DensityProvider";
import { ThemeProvider } from "../../app/providers/ThemeProvider";
import { usePreferencesStore } from "../../app/state/usePreferencesStore";
import { ToastProvider } from "../../app/providers/ToastProvider";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { NetworkStatusProvider } from "@/shared/network";
import {
  ContrastEnforcer,
  HighContrastProvider,
  LiveAnnouncerProvider,
  ReducedMotionProvider,
} from "@/shared/a11y";
import {
  AuthorshipProvider,
  type AuthorshipHighlightMode,
} from "@/shared/ui/authored-text";
import { useMaybeTrustView } from "@/shared/ui/trust-view";

function PersistentAuthorshipProvider({ children }: PropsWithChildren) {
  const trustView = useMaybeTrustView();
  const highlightMode = usePreferencesStore(
    (state) => state.authorshipHighlightMode,
  );
  const setHighlightMode = usePreferencesStore(
    (state) => state.setAuthorshipHighlightMode,
  );

  return (
    <AuthorshipProvider
      highlightMode={highlightMode}
      onHighlightModeChange={(nextMode: AuthorshipHighlightMode) => {
        startTransition(() => {
          setHighlightMode(nextMode);
        });
      }}
      trustDisplayMode={trustView?.mode}
    >
      {children}
    </AuthorshipProvider>
  );
}

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <LocaleProvider>
        <TelemetryProvider>
          <HighContrastProvider>
            <ReducedMotionProvider>
              <LiveAnnouncerProvider>
                <TemporalCursorProvider>
                  <CounterfactualProvider>
                    <TrustViewProvider>
                      <QuantityRuntimeProvider>
                        <ToastProvider>
                          <AlertDialogProvider>
                            <AuthSessionProvider>
                              <AuthzProvider>
                                <NetworkStatusProvider>
                                  <OfflineQueueProvider>
                                    <FeatureFlagProvider>
                                      <InterfaceModeProvider>
                                        <DensityProvider>
                                          <ThemeProvider>
                                            <PersistentAuthorshipProvider>
                                              {children}
                                              <ContrastEnforcer />
                                            </PersistentAuthorshipProvider>
                                          </ThemeProvider>
                                        </DensityProvider>
                                      </InterfaceModeProvider>
                                    </FeatureFlagProvider>
                                  </OfflineQueueProvider>
                                </NetworkStatusProvider>
                              </AuthzProvider>
                            </AuthSessionProvider>
                          </AlertDialogProvider>
                        </ToastProvider>
                      </QuantityRuntimeProvider>
                    </TrustViewProvider>
                  </CounterfactualProvider>
                </TemporalCursorProvider>
              </LiveAnnouncerProvider>
            </ReducedMotionProvider>
          </HighContrastProvider>
        </TelemetryProvider>
      </LocaleProvider>
    </QueryClientProvider>
  );
}
