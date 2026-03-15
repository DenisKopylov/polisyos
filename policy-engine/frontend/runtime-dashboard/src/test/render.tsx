import type { PropsWithChildren, ReactElement } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { FALLBACK_AUTH_ME } from "@/api/hooks/useAuthMe";
import { queryKeys } from "@/api/queryKeys";
import { AuthSessionProvider } from "@/app/auth/AuthSessionProvider";
import { AuthzProvider } from "@/app/authz/AuthzProvider";
import { AlertDialogProvider } from "@/app/providers/AlertDialogProvider";
import { FeatureFlagProvider } from "@/app/providers/FeatureFlagProvider";
import { LiveAnnouncerProvider } from "@/app/providers/LiveAnnouncerProvider";
import { TelemetryProvider } from "@/app/providers/TelemetryProvider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import { ToastProvider } from "@/app/providers/ToastProvider";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { createTestQueryClient } from "@/test/queryClient";

export function createAppRenderHarness() {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(queryKeys.authMe(), FALLBACK_AUTH_ME);

  function BaseProviders({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <LocaleProvider>
          <TelemetryProvider>
            <AuthSessionProvider>
              <AuthzProvider>
                <FeatureFlagProvider>
                  <ThemeProvider>{children}</ThemeProvider>
                </FeatureFlagProvider>
              </AuthzProvider>
            </AuthSessionProvider>
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
