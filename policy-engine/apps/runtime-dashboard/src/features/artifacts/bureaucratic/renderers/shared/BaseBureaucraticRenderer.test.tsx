import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { renderWithProviders } from "@/test/render";

import type { BureaucraticBlock } from "../../ast/bureaucratic-document-ast";
import { BureaucraticBlockView } from "./BaseBureaucraticRenderer";

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("BureaucraticBlockView Trust View authority", () => {
  it("does not mint verification from a lineage projection", () => {
    window.history.replaceState(null, "", "/?trust=expanded");

    renderWithProviders(<BureaucraticBlockView block={quantityBlock()} />);

    expect(screen.queryByText("verified")).not.toBeInTheDocument();
    expect(screen.getByTestId("quantity")).toHaveAttribute(
      "data-lineage-status",
      "verified",
    );
  });

  it("renders verification carried by generated owner metadata", () => {
    window.history.replaceState(null, "", "/?trust=expanded");
    const block = quantityBlock();
    if (!block.quantity) {
      throw new Error("quantity fixture must carry a quantity");
    }
    block.quantity.lineage.trust_metadata = {
      dispute_status: "none",
      freshness: "current",
      verification_status: "verified",
      verified_by: "runtime-verifier",
    };

    renderWithProviders(<BureaucraticBlockView block={block} />);

    expect(screen.getByText("verified")).toBeInTheDocument();
    expect(screen.getByText("runtime-verifier")).toBeInTheDocument();
  });
});

function quantityBlock(): BureaucraticBlock {
  return {
    authorship: {
      author: "PolicyOS",
      author_role: "system",
      reviewed_by_human: false,
    },
    epistemic_origin: "model_generated",
    id: "quantity-policy-cost",
    kind: "quantity",
    level: 1,
    quantity: {
      label: "Policy cost",
      lineage: {
        freshness: "current",
        id: "lineage-policy-cost",
        status: "verified",
      },
      metric_id: "policy_cost",
      point: 100,
      quantity_class: "decision",
      unit: { code: "USD", display: "USD", system: "ucum" },
    },
    title: "Policy cost",
  };
}
