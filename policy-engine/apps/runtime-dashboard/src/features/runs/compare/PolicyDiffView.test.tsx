import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockRuntimeGetSuccess } from "@/test/runtimeApi";
import { renderWithProviders } from "@/test/render";

import { PolicyDiffView } from "./PolicyDiffView";
import { policyDiffFixture } from "./fixtures";
import { toDisplayDeltas } from "./useDiffData";

const { exportJsonMock } = vi.hoisted(() => ({
  exportJsonMock: vi.fn(),
}));

vi.mock("@/shared/ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/ui")>();
  return { ...actual, exportJson: exportJsonMock };
});

afterEach(() => {
  vi.restoreAllMocks();
  exportJsonMock.mockReset();
});

describe("PolicyDiffView", () => {
  it("marks all comparison quantity slots informational without mutating the wire payload", () => {
    const wireDelta = policyDiffFixture.deltas?.[0];
    const [displayDelta] = toDisplayDeltas(policyDiffFixture);
    if (!wireDelta || !displayDelta) {
      throw new Error("comparison fixture must include a complete delta");
    }

    for (const slot of [
      "a",
      "b",
      "delta_absolute",
      "delta_relative",
    ] as const) {
      const wireValue = wireDelta[slot];
      const displayValue = displayDelta[slot];
      if (wireValue == null || displayValue == null) {
        throw new Error(`comparison fixture omitted quantity slot ${slot}`);
      }
      expect(displayValue.point).toBe(wireValue.point);
      expect(displayValue.profile_binding_status).toBe("not_established");
      expect(displayValue.profile_binding_temporal_scope).toEqual(
        policyDiffFixture.temporal_scope,
      );
    }

    expect(wireDelta.a).not.toHaveProperty("profile_binding_status");
  });

  it("refuses a malformed supplied profile instead of normalizing it to absence", () => {
    const wireDelta = policyDiffFixture.deltas?.[0];
    const wireQuantity = wireDelta?.a;
    if (!wireDelta || !wireQuantity) {
      throw new Error("comparison fixture must include its run-A quantity");
    }

    const malformedPayload = {
      ...policyDiffFixture,
      deltas: [
        {
          ...wireDelta,
          a: {
            ...wireQuantity,
            lineage: {
              ...wireQuantity.lineage,
              artifact_ref: {
                artifact_id: `sha256:${"a".repeat(64)}`,
                kind: "core.decision_packet",
                media_type: "application/json",
                manifest_profile_sha256: "malformed-profile",
              },
            },
          },
        },
      ],
    };

    expect(() => toDisplayDeltas(malformedPayload)).toThrow(
      "Comparison quantity carries an invalid selected artifact reference",
    );
  });

  it("exports the original comparison payload rather than its display projection", async () => {
    const getSpy = mockRuntimeGetSuccess(policyDiffFixture);
    const user = userEvent.setup();

    renderWithProviders(<PolicyDiffView runAId="run-a" runBId="run-b" />, {
      initialEntries: ["/compare/run-a/run-b"],
    });
    await screen.findByText("Comparison frame");
    await user.click(screen.getByRole("button", { name: /export json/i }));

    expect(exportJsonMock).toHaveBeenCalledWith(
      "policy-diff.json",
      expect.objectContaining({
        runAId: "run-a",
        runBId: "run-b",
        payload: policyDiffFixture,
      }),
    );
    await waitFor(() => expect(getSpy).toHaveBeenCalledTimes(1));
    expect(getSpy).toHaveBeenNthCalledWith(
      1,
      "/api/v1/runs/compare",
      expect.objectContaining({
        params: expect.objectContaining({
          query: expect.objectContaining({ a: "run-a", b: "run-b" }),
        }),
      }),
    );
  });

  it("keeps profileless comparison quantities numeric and prevents legacy lineage fallback", async () => {
    const getSpy = mockRuntimeGetSuccess(policyDiffFixture);
    const user = userEvent.setup();

    renderWithProviders(<PolicyDiffView runAId="run-a" runBId="run-b" />, {
      initialEntries: ["/compare/run-a/run-b"],
    });

    await screen.findByText("Comparison frame");
    const quantity = screen
      .getAllByTestId("quantity")
      .find(
        (element) =>
          element.getAttribute("data-quantity-metric-id") ===
          "employment_rate_delta",
      );
    if (!quantity) {
      throw new Error("comparison did not render its employment-rate quantity");
    }
    expect(quantity).toHaveAttribute(
      "data-profile-binding-status",
      "not_established",
    );
    expect(quantity).toHaveTextContent("0.18");

    await user.click(quantity);

    expect(
      await screen.findByTestId("popover-profile-binding-status"),
    ).toHaveTextContent("Profile binding not established");
    expect(
      screen.queryByTestId("trust-verification-status"),
    ).not.toBeInTheDocument();
    await waitFor(() => expect(getSpy).toHaveBeenCalledTimes(1));
    expect(getSpy).toHaveBeenNthCalledWith(
      1,
      "/api/v1/runs/compare",
      expect.objectContaining({
        params: expect.objectContaining({
          query: expect.objectContaining({ a: "run-a", b: "run-b" }),
        }),
      }),
    );
  });
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
