import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TrustViewProvider } from "@/app/providers/TrustViewProvider";
import { useTrustView } from "@/app/providers/useTrustView";
import { LocaleProvider } from "@/i18n/LocaleProvider";

import { TrustInspector } from "./TrustInspector";

function OpenInspectorButton() {
  const { openInspector } = useTrustView();
  return (
    <button
      type="button"
      onClick={() =>
        openInspector({
          hash: "sha256:abcdef0123456789",
          id: "artifact:fixture",
          kind: "quantity",
          label: "Effect size",
          trustMetadata: {
            dispute_status: "none",
            freshness: "current",
            hash: "sha256:abcdef0123456789",
            temporal_scope: {
              tx_at: "2026-04-16T09:20:00Z",
              valid_at: "2026-04-15T12:00:00Z",
            },
            verification_method: "lineage_hash_match",
            verification_status: "verified",
            verified_at: "2026-04-16T09:20:00Z",
            verified_by: "RiskReviewBot@2.0",
          },
        })
      }
    >
      open
    </button>
  );
}

describe("TrustInspector", () => {
  it("shows selected subject metadata and closes from the panel", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn();
    const open = vi.fn();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    vi.stubGlobal("open", open);
    window.history.pushState({}, "", "/runs/run_a?trust=compact");

    render(
      <LocaleProvider>
        <TrustViewProvider>
          <OpenInspectorButton />
          <TrustInspector />
        </TrustViewProvider>
      </LocaleProvider>,
    );

    await user.click(screen.getByRole("button", { name: "open" }));

    expect(screen.getByRole("dialog")).toHaveTextContent("Effect size");
    expect(screen.getByRole("dialog")).toHaveTextContent("RiskReviewBot@2.0");
    expect(screen.getByRole("dialog")).toHaveTextContent("lineage_hash_match");

    await user.click(
      screen.getByRole("button", { name: "Copy audit link" }),
    );
    expect(writeText).toHaveBeenCalledWith(
      expect.stringContaining("trust=expanded"),
    );
    expect(writeText).toHaveBeenCalledWith(
      expect.stringContaining("trust_subject=artifact%3Afixture"),
    );

    await user.click(screen.getByRole("button", { name: /Open deep dive/i }));
    expect(open).toHaveBeenCalledWith(
      "/api/v1/lineage/artifact%3Afixture",
      "_blank",
      "noopener,noreferrer",
    );

    await user.click(screen.getByRole("button", { name: "Export audit" }));
    expect(open).toHaveBeenCalledWith(
      "/api/v1/lineage/artifact%3Afixture/export/prov",
      "_blank",
      "noopener,noreferrer",
    );

    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
