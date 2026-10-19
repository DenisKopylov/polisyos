import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  lineageGraphFixture,
  profileTrustMetadataFixture,
} from "@/test/fixtures/profileLineageBatch";
import { mockRuntimeGetSuccess } from "@/test/runtimeApi";
import { renderWithProviders } from "@/test/render";
import { TrustInspector } from "@/shared/ui/trust-view";

import { Quantity } from "./Quantity";
import { formatQuantityValue } from "./quantity-format";
import type {
  LineageGraphView,
  LineageResponsePayload,
  QuantityValue,
} from "./quantity.types";

const meta: LineageResponsePayload["meta"] = {
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

const lineage: LineageGraphView = lineageGraphFixture({
  lineageId: "artifact:sha256:fixture",
  status: "verified",
  freshness: "current",
  hash: "sha256:abc",
  compactSummary: [
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
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("Quantity", () => {
  it("preserves unknown and incomparable outer-set values without scalar collapse", () => {
    renderWithProviders(
      <div>
        <Quantity
          value={{ ...verifiedQuantity, point: null }}
          provenanceMode="off"
        />
        <Quantity
          value={{ ...verifiedQuantity, point: null }}
          absentValue={
            <span data-testid="incomparable-outer-set">
              Incomparable: lower-support or upper-support
            </span>
          }
          absentValueLabel="Incomparable outer set: lower-support or upper-support"
          provenanceMode="off"
        />
      </div>,
    );

    const quantities = screen.getAllByTestId("quantity");
    expect(quantities[0]).toHaveAttribute(
      "data-quantity-presentation",
      "unknown",
    );
    expect(quantities[0]).toHaveTextContent("Unknown");
    expect(quantities[1]).toHaveAttribute(
      "data-quantity-presentation",
      "non-scalar",
    );
    expect(screen.getByTestId("incomparable-outer-set")).toBeInTheDocument();
    expect(quantities[1]).toHaveAccessibleName(
      /Incomparable outer set: lower-support or upper-support/u,
    );
    expect(quantities[0]).not.toHaveTextContent("0");
    expect(quantities[1]).not.toHaveTextContent("0");
  });

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

  it("keeps disputed uncertainty separate from lineage verification", () => {
    renderWithProviders(
      <Quantity
        provenanceMode="off"
        value={{
          ...verifiedQuantity,
          lineage: {
            ...verifiedQuantity.lineage,
            freshness: "stale",
            status: "verified",
          },
          uncertainty: { disputed: true, identifiability: "unknown" },
        }}
      />,
    );

    expect(screen.getByTestId("quantity")).toHaveAttribute(
      "data-lineage-status",
      "verified",
    );
    expect(
      screen.getByTestId("quantity-uncertainty-disputed"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("quantity")).toHaveAccessibleName(/stale/u);
    expect(screen.getByTestId("quantity")).toHaveAccessibleName(/disputed/u);
  });

  it("does not append a ratio unit to percent-formatted values", () => {
    renderWithProviders(
      <Quantity
        format="percent"
        precision={0}
        provenanceMode="off"
        value={verifiedQuantity}
      />,
    );

    expect(screen.getByTestId("quantity")).toHaveTextContent("23%");
    expect(screen.getByTestId("quantity")).not.toHaveTextContent("ratio");
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

  it("keeps embedded trust hidden until a selected-profile admission exists", () => {
    window.history.replaceState(null, "", "/runs/run-1?trust=expanded");
    const getSpy = mockRuntimeGetSuccess({
      meta,
      temporal_scope: verifiedQuantity.time,
      lineage,
    });
    renderWithProviders(
      <>
        <Quantity
          value={{
            ...verifiedQuantity,
            lineage: {
              ...verifiedQuantity.lineage,
              hash: "sha256:abcdef0123456789",
              trust_metadata: profileTrustMetadataFixture({
                temporalScope: verifiedQuantity.time,
                hash: "sha256:abcdef0123456789",
                verificationMethod: "lineage_hash_match",
                verifiedAt: "2026-04-16T09:20:00Z",
                verifiedBy: "RiskReviewBot@2.0",
              }),
            },
          }}
          precision={2}
        />
        <TrustInspector />
      </>,
    );

    expect(screen.getByTestId("quantity")).toHaveTextContent("0.23");
    expect(screen.getByTestId("quantity")).toHaveAttribute(
      "data-lineage-status",
      "verified",
    );
    expect(screen.queryByText(/sha256:abcdef01/)).not.toBeInTheDocument();
    expect(screen.queryByText("RiskReviewBot@2.0")).not.toBeInTheDocument();
    expect(screen.queryByText("lineage_hash_match")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("dialog", { name: "Trust inspector" }),
    ).not.toBeInTheDocument();
    expect(getSpy).not.toHaveBeenCalled();
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
