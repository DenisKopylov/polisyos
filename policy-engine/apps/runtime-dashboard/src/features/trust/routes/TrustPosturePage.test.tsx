import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

const artifactBytes = readFileSync(
  resolve(process.cwd(), "public/atlas/trust-claim-posture.v1.json"),
);

describe("TrustPosturePage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("defaults to PUBLIC and keeps claim-bearing values fixed across depth", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.resolve(new Response(artifactBytes, { status: 200 }))),
    );
    const { default: TrustPosturePage } = await import("./TrustPosturePage");
    const view = renderWithProviders(<TrustPosturePage />, {
      initialEntries: ["/trust"],
    });

    expect(await screen.findByTestId("trust-posture-page")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        view.container.querySelectorAll("[data-trust-claim-row]").length,
      ).toBeGreaterThan(0),
    );
    expect(screen.getByRole("button", { name: "Public" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    const claimBearingBefore = [
      ...view.container.querySelectorAll("[data-trust-claim-bearing]"),
    ].map((node) => node.textContent);
    fireEvent.click(screen.getByRole("button", { name: "Reviewer" }));
    const claimBearingAfter = [
      ...view.container.querySelectorAll("[data-trust-claim-bearing]"),
    ].map((node) => node.textContent);
    expect(claimBearingAfter).toEqual(claimBearingBefore);
    expect(
      view.container.querySelectorAll("[data-trust-evidence-detail]").length,
    ).toBeGreaterThan(0);
    expect(
      view.container.querySelector("[data-trust-evidence-values]"),
    ).toBeVisible();
  });

  it("fails visibly unavailable instead of retaining a previous posture", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.resolve(new Response("{}", { status: 200 }))),
    );
    const { default: TrustPosturePage } = await import("./TrustPosturePage");
    renderWithProviders(<TrustPosturePage />, { initialEntries: ["/trust"] });

    expect(
      await screen.findByTestId("trust-posture-unavailable"),
    ).toHaveTextContent(/unavailable/i);
    expect(screen.queryByTestId("trust-posture-register")).toBeNull();
  });
});
