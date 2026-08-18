import fs from "node:fs";
import path from "node:path";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import { renderWithProviders } from "@/test/render";

import {
  OUTER_SET_NO_ADMISSIBLE_RANKING_TOKEN,
  OUTER_SET_ORDER_UNAUTHORIZED_TOKEN,
  OuterSetValue,
} from "./OuterSetValue";

/**
 * DS16-C07 — properties of the real viz family beyond C01's three negatives.
 *
 * C01 proved the negatives non-vacuously and C07 makes real components satisfy them.
 * What is added here is the family's own structural commitments, which C01 could not
 * state because the family did not exist.
 */

function member(metricId: string, point: number | null): QuantityValueOutput {
  return {
    label: metricId,
    lineage: { freshness: "current", id: `lineage:${metricId}`, status: "verified" },
    metric_id: metricId,
    point,
    quantity_class: "decision",
    time: null,
    uncertainty: null,
    unit: { code: "1", display: "value", system: "ucum" },
  };
}

const TAIL = member("ds16.tail.worst_case", -0.9);
const BODY = member("ds16.body.central", 0.4);

describe("DS16-C07 set-valued viz family", () => {
  it("has no ranking code path at all, because no authorization type exists", () => {
    // Measured, not assumed: the family cannot rank because nothing can license it.
    const source = fs.readFileSync(
      path.join(import.meta.dirname, "OuterSetValue.tsx"),
      "utf8",
    );
    for (const orderingConstruct of [
      "<ol",
      "aria-posinset",
      "aria-setsize",
      "data-rank",
      ".sort(",
      "localeCompare",
    ]) {
      expect(
        source.includes(orderingConstruct),
        `the family must contain no ordering construct: ${orderingConstruct}`,
      ).toBe(false);
    }
  });

  it("keeps the two order statements distinct — values versus surface authority", () => {
    // `incomparable` is a claim about the VALUES and only a producer may make it.
    const producerVerdict = renderWithProviders(
      <OuterSetValue comparison="incomparable" members={[TAIL, BODY]} />,
    );
    expect(screen.getByTestId("ds16-order-statement")).toHaveTextContent(
      OUTER_SET_NO_ADMISSIBLE_RANKING_TOKEN,
    );
    expect(screen.getByTestId("ds16-comparison")).toHaveAttribute(
      "data-comparison",
      "incomparable",
    );
    producerVerdict.unmount();

    // Absent a verdict the surface says only what it may: nothing authorizes a ranking
    // here. Collapsing this into "incomparable" would have the glass assert a property
    // of the values it has no standing to assert.
    renderWithProviders(<OuterSetValue comparison={null} members={[TAIL, BODY]} />);
    expect(screen.getByTestId("ds16-order-statement")).toHaveTextContent(
      OUTER_SET_ORDER_UNAUTHORIZED_TOKEN,
    );
    expect(screen.getByTestId("ds16-comparison")).toHaveAttribute(
      "data-comparison",
      "unauthorized",
    );
    expect(OUTER_SET_ORDER_UNAUTHORIZED_TOKEN).not.toBe(
      OUTER_SET_NO_ADMISSIBLE_RANKING_TOKEN,
    );
  });

  it("never shows a tail as a cancelling average", () => {
    renderWithProviders(<OuterSetValue comparison={null} members={[TAIL, BODY]} />);

    // The mean of -0.9 and 0.4 is -0.25; a family that averaged would render it and
    // would render one value where two were supplied.
    expect(screen.queryByText("-0.25")).not.toBeInTheDocument();
    expect(screen.getByTestId("ds16-comparison")).toHaveAttribute(
      "data-outer-set-cardinality",
      "2",
    );
    expect(screen.getAllByTestId("quantity")).toHaveLength(2);
    expect(screen.getByText("-0.9")).toBeInTheDocument();
    expect(screen.getByText("0.4")).toBeInTheDocument();
  });

  it("declares its cardinality for every set, including a single member", () => {
    renderWithProviders(<OuterSetValue comparison={null} members={[BODY]} />);
    expect(screen.getByTestId("ds16-comparison")).toHaveAttribute(
      "data-outer-set-cardinality",
      "1",
    );
  });
});
