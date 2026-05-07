import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockRuntimeGetSuccess } from "@/test/runtimeApi";
import { renderWithProviders } from "@/test/render";
import { TrustViewProvider } from "@/app/providers/TrustViewProvider";
import { TrustInspector } from "@/shared/ui/trust-view";

import { Quantity } from "./Quantity";
import { formatQuantityValue } from "./quantity-format";
import type { LineageGraphView, QuantityValue } from "./quantity.types";

const meta = {
  generated_at: "2026-04-24T12:00:00Z",
  request_id: "req-quantity",
  source_kinds: ["core_run"],
};

const verifiedQuantity: QuantityValue = {
  point: 0.23456,
  unit: { code: "1", system: "ucum", display: "ratio" },
  metric_id: "employment_rate_delta",
  lineage: {
    id: "artifact:sha256:fixture",
    status: "verified",
    freshness: "current",
    summary: { source: "fixture" },
    compact_summary: [
      { kind: "source", label: "QES 2024 Q3" },
      { kind: "model", label: "DoubleML v2.1" },
      { kind: "result", label: "employment_rate_delta" },
    ],
  },
  uncertainty: {
    ci_95: [0.15, 0.31],
    method: "bootstrap",
    identifiability: "estimated",
    disputed: false,
  },
  time: {
    valid_at: "2026-04-15T12:00:00Z",
    tx_at: "2026-04-16T09:20:00Z",
  },
  quantity_class: "decision",
  label: "Effect size",
};

const lineage: LineageGraphView = {
  id: "artifact:sha256:fixture",
  status: "verified",
  freshness: "current",
  hash: "sha256:abc",
  compact_summary: [
    { kind: "source", label: "QES 2024 Q3", id: "n1" },
    { kind: "transform", label: "Winsorize", id: "n2" },
    { kind: "model", label: "DoubleML v2.1", id: "n3" },
    { kind: "result", label: "effect_size", id: "n4" },
  ],
  nodes: [
    {
      id: "artifact:sha256:source",
      kind: "dataset",
      label: "QES 2024 Q3",
      timestamp: "2026-04-15T12:00:00Z",
    },
  ],
  edges: [],
  exports: {
    openlineage: "/api/v1/lineage/artifact:sha256:fixture/export/openlineage",
    prov: "/api/v1/lineage/artifact:sha256:fixture/export/prov",
  },
};

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("Quantity", () => {
  it("renders the formatted value and unit from the envelope", () => {
    renderWithProviders(
      <Quantity value={verifiedQuantity} precision={2} provenanceMode="off" />,
    );

    expect(screen.getByText("0.23")).toBeInTheDocument();
    expect(screen.getByText("ratio")).toBeInTheDocument();
    expect(screen.getByTestId("quantity")).toHaveAttribute(
      "data-lineage-status",
      "verified",
    );
  });

  it("announces value, confidence interval, and provenance availability", () => {
    renderWithProviders(
      <Quantity value={verifiedQuantity} precision={2} provenanceMode="off" />,
    );

    expect(screen.getByTestId("quantity")).toHaveAccessibleName(
      "Effect size 0.23 ratio, 95 percent confidence interval 0.15 to 0.31, verified provenance available",
    );
  });

  it("marks disputed uncertainty as the visible status", () => {
    renderWithProviders(
      <Quantity
        provenanceMode="off"
        value={{
          ...verifiedQuantity,
          lineage: { ...verifiedQuantity.lineage, status: "verified" },
          uncertainty: { disputed: true },
        }}
      />,
    );

    expect(screen.getByTestId("quantity")).toHaveAttribute(
      "data-provenance-status",
      "disputed",
    );
  });

  it("formats unitless values without trailing unit text", () => {
    expect(
      formatQuantityValue({
        ...verifiedQuantity,
        point: 42,
        unit: { code: "1", system: "ucum", display: "value" },
      }).text,
    ).toBe("42");
  });

  it("opens provenance popover after the hover delay and lazy-loads lineage", async () => {
    vi.useFakeTimers();
    const getSpy = mockRuntimeGetSuccess({
      meta,
      temporal_scope: {
        valid_at: "2026-04-15T12:00:00Z",
        tx_at: "2026-04-16T09:20:00Z",
      },
      lineage,
    });
    renderWithProviders(<Quantity value={verifiedQuantity} precision={2} />);

    fireEvent.mouseEnter(screen.getByTestId("quantity"));
    expect(screen.queryByText("Provenance")).not.toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(151);
    });

    expect(screen.getByText("Provenance")).toBeInTheDocument();
    vi.useRealTimers();
    await waitFor(() => expect(getSpy).toHaveBeenCalled());
  });

  it("renders expanded Trust View metadata without fetching a different truth", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/runs/run-1?trust=expanded");
    renderWithProviders(
      <TrustViewProvider>
        <>
          <Quantity
            value={{
              ...verifiedQuantity,
              lineage: {
                ...verifiedQuantity.lineage,
                hash: "sha256:abcdef0123456789",
                trust_metadata: {
                  dispute_status: "none",
                  freshness: "current",
                  hash: "sha256:abcdef0123456789",
                  temporal_scope: verifiedQuantity.time,
                  verification_method: "lineage_hash_match",
                  verification_status: "verified",
                  verified_at: "2026-04-16T09:20:00Z",
                  verified_by: "RiskReviewBot@2.0",
                },
              },
            }}
            precision={2}
          />
          <TrustInspector />
        </>
      </TrustViewProvider>,
    );

    expect(screen.getByText(/sha256:abcdef01/)).toBeInTheDocument();
    expect(screen.getByText("RiskReviewBot@2.0")).toBeInTheDocument();
    expect(screen.getByText("lineage_hash_match")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "verified" }));
    expect(
      screen.getByRole("dialog", { name: "Trust inspector" }),
    ).toHaveTextContent("Effect size");
  });

  it("opens deep dive from the active popover keyboard path", async () => {
    const user = userEvent.setup();
    mockRuntimeGetSuccess({ meta, temporal_scope: null, lineage });
    renderWithProviders(<Quantity value={verifiedQuantity} precision={2} />);

    await user.tab();
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Provenance")).toBeInTheDocument();

    await user.keyboard("d");
    expect(await screen.findByText("Provenance deep dive")).toBeInTheDocument();
  });
});
