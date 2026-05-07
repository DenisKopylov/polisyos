import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import {
  TemporalCursorProvider,
  useTemporalCursor,
} from "@/app/providers/TemporalCursorProvider";
import { createTestQueryClient } from "@/test/queryClient";
import { ReducedMotionProvider } from "@/shared/a11y";
import { TemporalScrubber } from "./TemporalScrubber";

const meta = {
  title: "Shared UI/TemporalScrubber",
  component: TemporalScrubber,
  decorators: [
    (Story) => (
      <QueryClientProvider client={createTestQueryClient()}>
        <ReducedMotionProvider>
          <TemporalCursorProvider>
            <TemporalStoryFrame>
              <Story />
            </TemporalStoryFrame>
          </TemporalCursorProvider>
        </ReducedMotionProvider>
      </QueryClientProvider>
    ),
  ],
} satisfies Meta<typeof TemporalScrubber>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    labels: {
      now: "Now",
      observed: "Observed",
      simulated: "Simulated",
      slider: "Temporal cursor",
    },
  },
};

function TemporalStoryFrame({ children }: { children: ReactNode }) {
  const { setTemporalCapabilities } = useTemporalCursor();
  useEffect(() => {
    setTemporalCapabilities({
      defaultScope: {
        txAt: "2026-04-16T09:20:00Z",
        validAt: "2026-04-15T12:00:00Z",
      },
      eventPoints: [
        {
          id: "policy-change",
          kind: "policy_change",
          label: "policy change",
          timestamp: "2026-04-12T09:00:00Z",
        },
        {
          id: "correction",
          kind: "correction",
          label: "correction",
          timestamp: "2026-04-16T09:20:00Z",
        },
      ],
      resolution: "event",
      runId: "run-story",
      surfaces: [],
      txRange: {
        earliest: "2026-04-10T00:00:00Z",
        latest: "2026-04-20T00:00:00Z",
      },
      validRange: {
        earliest: "2026-04-10T00:00:00Z",
        latest: "2026-04-20T00:00:00Z",
      },
    });
  }, [setTemporalCapabilities]);
  return <div className="bg-surface p-4">{children}</div>;
}
