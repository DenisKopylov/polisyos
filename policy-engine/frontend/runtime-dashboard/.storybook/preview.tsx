import type { Preview } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";

import { AlertDialogProvider } from "@/app/providers/AlertDialogProvider";
import { FeatureFlagProvider } from "@/app/providers/FeatureFlagProvider";
import { LiveAnnouncerProvider } from "@/app/providers/LiveAnnouncerProvider";
import { TelemetryProvider } from "@/app/providers/TelemetryProvider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import { ToastProvider } from "@/app/providers/ToastProvider";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import "@/styles.css";

const preview: Preview = {
  decorators: [
    (Story) => (
      <MemoryRouter>
        <LocaleProvider>
          <TelemetryProvider>
            <LiveAnnouncerProvider>
              <ToastProvider>
                <AlertDialogProvider>
                  <FeatureFlagProvider>
                    <ThemeProvider>
                      <div className="text-text min-h-screen bg-[radial-gradient(circle_at_top,var(--page-glow-teal),transparent_38%),linear-gradient(180deg,var(--page-gradient-start)_0%,var(--page-gradient-end)_100%)] p-6">
                        <div className="mx-auto max-w-6xl">
                          <Story />
                        </div>
                      </div>
                    </ThemeProvider>
                  </FeatureFlagProvider>
                </AlertDialogProvider>
              </ToastProvider>
            </LiveAnnouncerProvider>
          </TelemetryProvider>
        </LocaleProvider>
      </MemoryRouter>
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
};

export default preview;
