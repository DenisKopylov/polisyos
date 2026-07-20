import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";

import {
  TemporalRuntimeBridgeProvider,
  type TemporalRuntimeBridgeValue,
} from "./TemporalRuntimeBridge";

const range = { earliest: null, latest: null };

const value: TemporalRuntimeBridgeValue = {
  capabilities: null,
  committedScope: null,
  commitPreview: () => undefined,
  commitScope: () => undefined,
  effectiveScope: null,
  eventPoints: [],
  previewScope: null,
  range,
  resetScope: () => undefined,
  setPreviewScope: () => undefined,
  setTemporalCapabilities: () => undefined,
  stepValidTime: () => undefined,
  txRange: range,
};

describe("TemporalRuntimeBridgeProvider accessibility", () => {
  it("adds no accessibility violations around consumer content", async () => {
    const { container } = render(
      <TemporalRuntimeBridgeProvider value={value}>
        <p>Temporal consumer</p>
      </TemporalRuntimeBridgeProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
