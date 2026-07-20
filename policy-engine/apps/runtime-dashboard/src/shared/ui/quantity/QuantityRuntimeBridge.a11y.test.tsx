import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";

import {
  QuantityRuntimeBridgeProvider,
  type QuantityRuntimeBridgeValue,
} from "./QuantityRuntimeBridge";

const unavailable = () => Promise.reject(new Error("not invoked"));

const value: QuantityRuntimeBridgeValue = {
  fetchLineage: unavailable,
  fetchLineageBatch: unavailable,
  fetchLineageExport: unavailable,
  temporalScope: null,
  trustMode: "off",
};

describe("QuantityRuntimeBridgeProvider accessibility", () => {
  it("adds no accessibility violations around consumer content", async () => {
    const { container } = render(
      <QuantityRuntimeBridgeProvider value={value}>
        <p>Quantity consumer</p>
      </QuantityRuntimeBridgeProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
