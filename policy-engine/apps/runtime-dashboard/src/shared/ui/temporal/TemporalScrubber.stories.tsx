import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ReactNode } from "react";

import { ReducedMotionProvider } from "@/shared/a11y";
import {
  TemporalRuntimeBridgeProvider,
  type TemporalRuntimeBridgeValue,
} from "./TemporalRuntimeBridge";
import { TemporalScrubber } from "./TemporalScrubber";

const RANGE = {
  earliest: "2026-04-10T00:00:00Z",
  latest: "2026-04-20T00:00:00Z",
};

const value: TemporalRuntimeBridgeValue = {
  capabilities: {
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
    txRange: RANGE,
    validRange: RANGE,
  },
  committedScope: null,
  commitPreview: () => undefined,
  commitScope: () => undefined,
  effectiveScope: {
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
  previewScope: null,
  range: RANGE,
  resetScope: () => undefined,
  setPreviewScope: () => undefined,
  setTemporalCapabilities: () => undefined,
  stepValidTime: () => undefined,
  txRange: RANGE,
};

const meta = {
  title: "Shared UI/TemporalScrubber",
  component: TemporalScrubber,
  decorators: [
    (Story) => (
      <ReducedMotionProvider>
        <TemporalRuntimeBridgeProvider value={value}>
          <TemporalStoryFrame>
            <Story />
          </TemporalStoryFrame>
        </TemporalRuntimeBridgeProvider>
      </ReducedMotionProvider>
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
  return <div className="bg-surface p-4">{children}</div>;
}
