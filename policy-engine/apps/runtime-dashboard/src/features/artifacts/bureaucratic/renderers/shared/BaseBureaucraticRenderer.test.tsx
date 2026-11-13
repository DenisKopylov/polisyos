import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { VerificationMetadata } from "@polisyos/runtime-api-client";
import { TrustInspector } from "@/shared/ui/trust-view";
import { renderWithProviders } from "@/test/render";

import type { BureaucraticBlock } from "../../ast/bureaucratic-document-ast";
import { BureaucraticBlockView } from "./BaseBureaucraticRenderer";

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("BureaucraticBlockView Trust View authority", () => {
  it("does not mint verification from a lineage projection", () => {
    window.history.replaceState(null, "", "/?trust=expanded");

    renderWithProviders(
      <>
        <BureaucraticBlockView block={quantityBlock()} />
        <TrustInspector />
      </>,
    );

    expect(screen.getByTestId("quantity")).toHaveAttribute(
      "data-lineage-status",
      "verified",
    );
    expect(screen.queryByTestId("trust-verification-status")).toBeNull();
    expect(
      screen.queryByRole("dialog", { name: "Trust inspector" }),
    ).toBeNull();
  });

  it("keeps unbound owner metadata out of content-bound Trust View", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/?trust=expanded");
    const block = quantityBlock();
    if (!block.quantity) {
      throw new Error("quantity fixture must carry a quantity");
    }
    const ownerMetadata = {
      dispute_status: "none",
      freshness: "current",
      verification_status: "verified",
      verified_by: "runtime-verifier",
    } satisfies VerificationMetadata;
    block.quantity.lineage.trust_metadata = ownerMetadata;

    renderWithProviders(
      <>
        <BureaucraticBlockView block={block} />
        <TrustInspector />
      </>,
    );

    const quantityOpener = screen.getByRole("button", {
      name: "Policy cost 100 USD, verified provenance available",
    });
    expect(quantityOpener).toHaveAttribute("data-lineage-status", "verified");
    await user.click(quantityOpener);
    const provenancePopover = await screen.findByRole("dialog");
    expect(
      within(provenancePopover).getByTestId("lineage-verification-status"),
    ).toHaveTextContent("verified");
    expect(
      within(provenancePopover).queryByTestId("trust-verification-status"),
    ).toBeNull();
    expect(block.quantity.lineage.trust_metadata).toEqual(ownerMetadata);
    expect(screen.queryByText("runtime-verifier")).toBeNull();
    expect(
      screen.queryByRole("dialog", { name: "Trust inspector" }),
    ).toBeNull();
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
