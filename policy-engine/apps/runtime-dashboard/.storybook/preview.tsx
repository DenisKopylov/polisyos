import type { PropsWithChildren } from "react";
import type { Preview } from "@storybook/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { queryClient } from "@/api/queryClient";
import { AlertDialogProvider } from "@/app/providers/AlertDialogProvider";
import { DensityProvider } from "@/app/providers/DensityProvider";
import { FeatureFlagProvider } from "@/app/providers/FeatureFlagProvider";
import { TelemetryProvider } from "@/app/providers/TelemetryProvider";
import {
  ThemeProvider,
  THEME_STORAGE_KEY,
} from "@/app/providers/ThemeProvider";
import { PREFERENCES_STORAGE_KEY } from "@/app/state/usePreferencesStore";
import { ToastProvider } from "@/app/providers/ToastProvider";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import {
  HighContrastProvider,
  LiveAnnouncerProvider,
  ReducedMotionProvider,
} from "@/shared/a11y";
import { AuthorshipProvider } from "@/shared/ui/authored-text";
import "@/styles.css";

function StorybookAppearanceBoundary({
  children,
  density,
  theme,
}: PropsWithChildren<{
  density: "comfortable" | "compact" | "condensed";
  theme: "light" | "dark" | "high-contrast";
}>) {
  if (typeof globalThis.window !== "undefined") {
    const resolvedTheme = theme === "high-contrast" ? "light" : theme;
    globalThis.window.localStorage.setItem(THEME_STORAGE_KEY, resolvedTheme);
    globalThis.window.localStorage.setItem(
      PREFERENCES_STORAGE_KEY,
      JSON.stringify({
        state: { authorshipHighlightMode: "subtle", density },
        version: 3,
      }),
    );
    globalThis.document.documentElement.dataset.contrast =
      theme === "high-contrast" ? "high" : "standard";
  }

  return children;
}

const preview: Preview = {
  decorators: [
    (Story, context) => (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LocaleProvider>
            <TelemetryProvider>
              <HighContrastProvider>
                <ReducedMotionProvider>
                  <LiveAnnouncerProvider>
                    <ToastProvider>
                      <AlertDialogProvider>
                        <FeatureFlagProvider>
                          <StorybookAppearanceBoundary
                            key={`${context.globals.theme}-${context.globals.density}`}
                            density={context.globals.density}
                            theme={context.globals.theme}
                          >
                            <DensityProvider>
                              <ThemeProvider>
                                <AuthorshipProvider highlightMode="subtle">
                                  <div className="text-text min-h-screen bg-[radial-gradient(circle_at_top,var(--page-glow-teal),transparent_38%),linear-gradient(180deg,var(--page-gradient-start)_0%,var(--page-gradient-end)_100%)] p-6">
                                    <div className="mx-auto max-w-6xl">
                                      <Story />
                                    </div>
                                  </div>
                                </AuthorshipProvider>
                              </ThemeProvider>
                            </DensityProvider>
                          </StorybookAppearanceBoundary>
                        </FeatureFlagProvider>
                      </AlertDialogProvider>
                    </ToastProvider>
                  </LiveAnnouncerProvider>
                </ReducedMotionProvider>
              </HighContrastProvider>
            </TelemetryProvider>
          </LocaleProvider>
        </MemoryRouter>
      </QueryClientProvider>
    ),
  ],
  parameters: {
    layout: "fullscreen",
    controls: {
      expanded: true,
    },
    backgrounds: {
      disable: true,
    },
  },
  globalTypes: {
    theme: {
      defaultValue: "light",
      description: "Preview theme",
      toolbar: {
        icon: "mirror",
        items: [
          { value: "light", title: "Light" },
          { value: "dark", title: "Dark" },
          { value: "high-contrast", title: "High contrast" },
        ],
      },
    },
    density: {
      defaultValue: "comfortable",
      description: "Preview density",
      toolbar: {
        icon: "sidebar",
        items: [
          { value: "comfortable", title: "Comfortable" },
          { value: "compact", title: "Compact" },
          { value: "condensed", title: "Condensed" },
        ],
      },
    },
  },
};

export default preview;
