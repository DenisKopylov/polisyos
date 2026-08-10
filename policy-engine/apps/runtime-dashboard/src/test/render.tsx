import type { PropsWithChildren, ReactElement } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { AuthSessionProvider } from "@/app/auth/AuthSessionProvider";
import { AuthzProvider } from "@/app/authz/AuthzProvider";
import { AlertDialogProvider } from "@/app/providers/AlertDialogProvider";
import { DensityProvider } from "@/app/providers/DensityProvider";
import { FeatureFlagProvider } from "@/app/providers/FeatureFlagProvider";
import { InterfaceModeProvider } from "@/app/providers/InterfaceModeProvider";
import { TelemetryProvider } from "@/app/providers/TelemetryProvider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import { ToastProvider } from "@/app/providers/ToastProvider";
import { TrustViewProvider } from "@/app/providers/TrustViewProvider";
import { QuantityRuntimeProvider } from "@/app/providers/QuantityRuntimeProvider";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import {
  HighContrastProvider,
  LiveAnnouncerProvider,
  ReducedMotionProvider,
} from "@/shared/a11y";
import { AuthorshipProvider } from "@/shared/ui/authored-text";
import { createTestQueryClient } from "@/test/queryClient";
import { TEST_AUTH_ME } from "@/test/fixtures/authMe";

export function createAppRenderHarness() {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(queryKeys.authMe(), TEST_AUTH_ME);

  function BaseProviders({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <LocaleProvider>
          <TelemetryProvider>
            <HighContrastProvider>
              <ReducedMotionProvider>
                <AuthSessionProvider>
                  <AuthzProvider>
                    <FeatureFlagProvider>
                      <InterfaceModeProvider>
                        <DensityProvider>
                          <TrustViewProvider>
                            <QuantityRuntimeProvider>
                              <ThemeProvider>
                                <AuthorshipProvider>
                                  {children}
                                </AuthorshipProvider>
                              </ThemeProvider>
                            </QuantityRuntimeProvider>
                          </TrustViewProvider>
                        </DensityProvider>
                      </InterfaceModeProvider>
                    </FeatureFlagProvider>
                  </AuthzProvider>
                </AuthSessionProvider>
              </ReducedMotionProvider>
            </HighContrastProvider>
          </TelemetryProvider>
        </LocaleProvider>
      </QueryClientProvider>
    );
  }

  return {
    queryClient,
    baseWrapper: BaseProviders,
  };
}

export function renderWithProviders(
  ui: ReactElement,
  options?: {
    initialEntries?: string[];
    interactiveProviders?: boolean;
  },
) {
  const { queryClient, baseWrapper: BaseProviders } = createAppRenderHarness();

  function InteractiveProviders({ children }: PropsWithChildren) {
    return (
      <LiveAnnouncerProvider>
        <ToastProvider>
          <AlertDialogProvider>{children}</AlertDialogProvider>
        </ToastProvider>
      </LiveAnnouncerProvider>
    );
  }

  function Wrapper({ children }: PropsWithChildren) {
    const content = options?.interactiveProviders ? (
      <InteractiveProviders>{children}</InteractiveProviders>
    ) : (
      children
    );

    return (
      <MemoryRouter initialEntries={options?.initialEntries}>
        <BaseProviders>{content}</BaseProviders>
      </MemoryRouter>
    );
  }

  return {
    queryClient,
    ...render(ui, { wrapper: Wrapper }),
  };
}
