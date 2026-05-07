import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockRuntimeGetSuccess } from "@/test/runtimeApi";
import { renderWithProviders } from "@/test/render";

import { PolicyDiffView } from "./PolicyDiffView";
import { policyDiffFixture } from "./fixtures";

describe("PolicyDiffView", () => {
  it("renders comparison frame, delta rail and widgets from the compare endpoint", async () => {
    const getSpy = mockRuntimeGetSuccess(policyDiffFixture);

    renderWithProviders(<PolicyDiffView runAId="run-a" runBId="run-b" />, {
      initialEntries: ["/compare/run-a/run-b"],
    });

    expect(await screen.findByTestId("policy-diff-view")).toBeInTheDocument();
    expect(await screen.findByText("Comparison frame")).toBeInTheDocument();
    expect(screen.getByText("Causal deltas")).toBeInTheDocument();
    expect(screen.getAllByText("Employment rate").length).toBeGreaterThan(0);
    expect(screen.getByText("Provenance drift")).toBeInTheDocument();

    await waitFor(() =>
      expect(getSpy).toHaveBeenCalledWith(
        "/api/v1/runs/compare",
        expect.objectContaining({
          params: expect.objectContaining({
            query: expect.objectContaining({ a: "run-a", b: "run-b" }),
          }),
        }),
      ),
    );
  });

  it("reproduces selected metric from URL and updates the deep link on selection", async () => {
    mockRuntimeGetSuccess(policyDiffFixture);
    const user = userEvent.setup();

    renderWithProviders(<PolicyDiffView runAId="run-a" runBId="run-b" />, {
      initialEntries: ["/compare/run-a/run-b?metric=policy_cost"],
    });

    await waitFor(() =>
      expect(screen.getByTestId("policy-diff-view")).toHaveAttribute(
        "data-active-metric-id",
        "policy_cost",
      ),
    );

    await user.click(screen.getByRole("button", { name: /Employment rate/i }));

    expect(screen.getByTestId("policy-diff-view")).toHaveAttribute(
      "data-active-metric-id",
      "employment_rate_delta",
    );
  });

  it("renders the blocked state without deltas", async () => {
    mockRuntimeGetSuccess({
      ...policyDiffFixture,
      comparability: {
        status: "blocked",
        warnings: [],
        blocked_reasons: ["same_run"],
      },
      deltas: [],
    });

    renderWithProviders(<PolicyDiffView runAId="run-a" runBId="run-a" />);

    expect(
      await screen.findByText("No safe deltas to render"),
    ).toBeInTheDocument();
    expect(screen.getByText("same_run")).toBeInTheDocument();
  });
});
