import type { PropsWithChildren } from "react";
import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";

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
    defaultScope: { validAt: "2026-04-15T00:00:00Z" },
    eventPoints: [],
    resolution: "event",
    runId: "run-1",
    surfaces: [],
    txRange: RANGE,
    validRange: RANGE,
  },
  committedScope: null,
  commitPreview: () => undefined,
  commitScope: () => undefined,
  effectiveScope: { validAt: "2026-04-15T00:00:00Z" },
  eventPoints: [],
  previewScope: null,
  range: RANGE,
  resetScope: () => undefined,
  setPreviewScope: () => undefined,
  setTemporalCapabilities: () => undefined,
  stepValidTime: () => undefined,
  txRange: RANGE,
};

function Wrapper({ children }: PropsWithChildren) {
  return (
    <ReducedMotionProvider>
      <TemporalRuntimeBridgeProvider value={value}>
        {children}
      </TemporalRuntimeBridgeProvider>
    </ReducedMotionProvider>
  );
}

describe("TemporalScrubber accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    const { container } = render(
      <TemporalScrubber
        labels={{
          now: "Now",
          observed: "Observed",
          simulated: "Simulated",
          slider: "Temporal cursor",
        }}
      />,
      { wrapper: Wrapper },
    );
    const results = await axe(container);

    expect(results.violations).toHaveLength(0);
  });
});
