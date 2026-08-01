import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ComponentProps } from "react";
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import { renderWithProviders } from "@/test/render";
import { FactorImportanceChart } from "@/shared/ui/compounds/FactorImportanceChart";
import { SensitivityPlot } from "@/shared/ui/compounds/SensitivityPlot";

import { AnimatedNumber } from "./AnimatedNumber";
import { BSTSVisualization } from "./BSTSVisualization";
import { DiDVisualization } from "./DiDVisualization";
import { ForestPlot } from "./ForestPlot";
import {
  ChartQuantityEvidence,
  chartQuantityInterval,
  chartQuantityMembers,
  chartQuantityScalarPoint,
} from "./quantityChartSemantics";
import { SpecificationCurveChart } from "./SpecificationCurveChart";
import { SyntheticControlViz } from "./SyntheticControlViz";

function quantity(
  metricId: string,
  overrides: Partial<QuantityValueOutput> = {},
): QuantityValueOutput {
  return {
    label: metricId,
    lineage: {
      freshness: "current",
      id: `lineage:${metricId}`,
      status: "verified",
    },
    metric_id: metricId,
    point: null,
    quantity_class: "decision",
    time: null,
    uncertainty: null,
    unit: { code: "1", display: "value", system: "ucum" },
    ...overrides,
  };
}

const distribution = quantity("distribution-reference", {
  uncertainty: {
    disputed: false,
    identifiability: "estimated",
    method: "simulation",
    quantiles: { p10: -0.4, p50: 0.1, p90: 0.8 },
  },
});

const interval = quantity("interval-reference", {
  uncertainty: {
    ci_95: [-0.2, 0.6],
    disputed: false,
    identifiability: "estimated",
    method: "analytic",
  },
});

const pointNullEvidence = quantity("point-null-evidence", {
  uncertainty: {
    ci_80: [-0.15, 0.35],
    ci_95: [-0.2, 0.6],
    disputed: false,
    identifiability: "estimated",
    method: "simulation",
    quantiles: {
      owner_lower_tail: -0.41,
      owner_median_key: 0,
      owner_upper_tail: 0.83,
    },
  },
});

const zeroReference = quantity("zero-reference", { point: 0 });

const unknown = quantity("unknown-reference");
const lowerSupport = quantity("lower-support", { point: -0.3 });
const upperSupport = quantity("upper-support", { point: 0.7 });
const incomparable = [lowerSupport, upperSupport] as const;

type C07Resolution = {
  classification: "layout_geometry" | "quantity_semantics";
  closure_test_ref: string;
  origin_identity: { path: string };
  semantic_kind: "decision_bearing" | "non_authority_control";
};

const c07Resolutions = (
  JSON.parse(
    readFileSync(
      resolve(
        process.cwd(),
        "../../architecture/atlas_surfaces/frontend-baseline-debt-manifest.json",
      ),
      "utf8",
    ),
  ) as { lint: { resolutions: Array<C07Resolution & { cluster_id: string }> } }
).lint.resolutions.filter((resolution) => resolution.cluster_id === "C07");

describe("chart quantity semantics", () => {
  it("preserves every finite point-null evidence entry through Quantity", () => {
    renderWithProviders(<ChartQuantityEvidence value={pointNullEvidence} />);

    const evidence = screen.getByTestId("quantity");
    expect(evidence).toHaveTextContent("owner_lower_tail: -0.41");
    expect(evidence).toHaveTextContent("owner_median_key: 0");
    expect(evidence).toHaveTextContent("owner_upper_tail: 0.83");
    expect(evidence).toHaveTextContent("ci_95: [-0.2, 0.6]");
    expect(evidence).toHaveTextContent("ci_80: [-0.15, 0.35]");
    expect(evidence).toHaveAccessibleName(
      /owner_lower_tail: -0\.41.*owner_median_key: 0.*owner_upper_tail: 0\.83.*ci_95: \[-0\.2, 0\.6\].*ci_80: \[-0\.15, 0\.35\]/u,
    );
    expect(evidence).not.toHaveTextContent("Unknown");
  });

  it("accepts only the AnimatedNumber format option it forwards", () => {
    const forwarded: ComponentProps<typeof AnimatedNumber>["formatOptions"] = {
      maximumFractionDigits: 2,
    };
    expect(forwarded).toEqual({ maximumFractionDigits: 2 });

    const unsupported: ComponentProps<typeof AnimatedNumber>["formatOptions"] =
      {
        // @ts-expect-error AnimatedNumber does not forward currency formatting.
        currency: "EUR",
      };
    expect(unsupported).toEqual({ currency: "EUR" });
  });

  it("preserves distribution interval unknown and incomparable chart values without scalar collapse", () => {
    expect(c07Resolutions).toHaveLength(37);
    expect(
      c07Resolutions.reduce<Record<string, number>>((counts, resolution) => {
        counts[resolution.classification] =
          (counts[resolution.classification] ?? 0) + 1;
        return counts;
      }, {}),
    ).toEqual({ layout_geometry: 33, quantity_semantics: 4 });
    expect(
      c07Resolutions.reduce<Record<string, number>>((counts, resolution) => {
        counts[resolution.origin_identity.path] =
          (counts[resolution.origin_identity.path] ?? 0) + 1;
        return counts;
      }, {}),
    ).toEqual({
      "apps/runtime-dashboard/src/shared/charts/AnimatedNumber.tsx": 1,
      "apps/runtime-dashboard/src/shared/charts/BSTSVisualization.tsx": 13,
      "apps/runtime-dashboard/src/shared/charts/DiDVisualization.tsx": 7,
      "apps/runtime-dashboard/src/shared/charts/ForestPlot.tsx": 1,
      "apps/runtime-dashboard/src/shared/charts/SpecificationCurveChart.tsx": 1,
      "apps/runtime-dashboard/src/shared/charts/SyntheticControlViz.tsx": 12,
      "apps/runtime-dashboard/src/shared/ui/compounds/FactorImportanceChart.tsx": 1,
      "apps/runtime-dashboard/src/shared/ui/compounds/SensitivityPlot.tsx": 1,
    });
    expect(
      c07Resolutions.every(
        (resolution) =>
          resolution.semantic_kind ===
          (resolution.classification === "quantity_semantics"
            ? "decision_bearing"
            : "non_authority_control"),
      ),
    ).toBe(true);
    expect(
      c07Resolutions.every(
        (resolution) =>
          resolution.closure_test_ref ===
          "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.test.tsx",
      ),
    ).toBe(true);

    expect(chartQuantityMembers(distribution)).toEqual([distribution]);
    expect(chartQuantityMembers(interval)).toEqual([interval]);
    expect(chartQuantityMembers(unknown)).toEqual([unknown]);
    expect(chartQuantityMembers(incomparable)).toEqual(incomparable);

    expect(chartQuantityScalarPoint(distribution)).toBeNull();
    expect(chartQuantityScalarPoint(interval)).toBeNull();
    expect(chartQuantityScalarPoint(unknown)).toBeNull();
    expect(chartQuantityScalarPoint(incomparable)).toBeNull();
    expect(chartQuantityScalarPoint(zeroReference)).toBe(0);
    expect(chartQuantityInterval(interval)).toEqual([-0.2, 0.6]);

    renderWithProviders(
      <div>
        <ChartQuantityEvidence value={distribution} />
        <ChartQuantityEvidence value={interval} />
        <ChartQuantityEvidence value={unknown} />
        <ChartQuantityEvidence value={incomparable} />
        <AnimatedNumber value={unknown} />
        <ForestPlot
          estimates={[
            {
              ci: { level: 0.95, lower: -0.2, upper: 0.6 },
              estimate: 0.1,
              id: "forest-estimate",
              label: "Forest estimate",
            },
          ]}
          referenceValue={interval}
        />
        <ForestPlot
          estimates={[
            {
              ci: { level: 0.95, lower: -0.2, upper: 0.6 },
              estimate: 0.1,
              id: "forest-zero-estimate",
              label: "Forest zero estimate",
            },
          ]}
          referenceValue={zeroReference}
        />
        <SpecificationCurveChart
          specifications={[
            {
              ci: { level: 0.95, lower: -0.2, upper: 0.6 },
              estimate: 0.1,
              id: "specification-estimate",
            },
          ]}
          referenceValue={distribution}
        />
        <SpecificationCurveChart
          specifications={[
            {
              ci: { level: 0.95, lower: -0.2, upper: 0.6 },
              estimate: 0.1,
              id: "specification-zero-estimate",
            },
          ]}
          referenceValue={zeroReference}
        />
        <SensitivityPlot
          points={[{ gamma: 1, lowerBound: -0.2, upperBound: 0.6 }]}
          referenceValue={incomparable}
        />
        <SensitivityPlot
          points={[{ gamma: 1, lowerBound: -0.2, upperBound: 0.6 }]}
          referenceValue={zeroReference}
        />
        <BSTSVisualization
          data={[
            { actual: 1, predicted: 0.9, time: "before" },
            { actual: 1.2, predicted: 1, time: "after" },
          ]}
          interventionTime="after"
        />
        <DiDVisualization
          control={{
            id: "control",
            label: "Control",
            postTreatment: 1.1,
            preTreatment: 1,
          }}
          treated={{
            id: "treated",
            label: "Treated",
            postTreatment: 1.4,
            preTreatment: 1,
          }}
          treatmentTime="after"
        />
        <SyntheticControlViz
          data={[
            { actual: 1, synthetic: 0.9, time: "before" },
            { actual: 1.2, synthetic: 1, time: "after" },
          ]}
          treatmentTime="after"
        />
        <FactorImportanceChart
          factors={[
            { direction: "positive", importance: 0.4, label: "Factor A" },
          ]}
        />
      </div>,
    );

    const renderedQuantities = screen.getAllByTestId("quantity");
    const renderedMetricIds = renderedQuantities.map((node) =>
      node.getAttribute("data-quantity-metric-id"),
    );
    expect(renderedMetricIds).toContain("distribution-reference");
    expect(renderedMetricIds).toContain("interval-reference");
    expect(renderedMetricIds).toContain("unknown-reference");
    expect(renderedMetricIds).toContain("lower-support");
    expect(renderedMetricIds).toContain("upper-support");
    const animatedEvidence = screen.getByTestId("animated-number");
    expect(
      within(animatedEvidence)
        .getAllByTestId("quantity")
        .map((node) => node.getAttribute("data-quantity-metric-id")),
    ).toEqual(["unknown-reference"]);
    const forestEvidence = screen.getAllByTestId("forest-reference-evidence");
    expect(
      within(forestEvidence[0]!)
        .getAllByTestId("quantity")
        .map((node) => node.getAttribute("data-quantity-metric-id")),
    ).toEqual(["interval-reference"]);
    expect(
      screen.getByRole("img", {
        name: "Forest plot with 1 studies. Direction relative to a reference is unavailable.",
      }),
    ).not.toContainElement(forestEvidence[0]!);
    const specificationEvidence = screen.getAllByTestId(
      "specification-reference-evidence",
    );
    expect(
      within(specificationEvidence[0]!)
        .getAllByTestId("quantity")
        .map((node) => node.getAttribute("data-quantity-metric-id")),
    ).toEqual(["distribution-reference"]);
    expect(
      screen.getByRole("img", {
        name: "Specification curve chart. 1 specifications.",
      }),
    ).not.toContainElement(specificationEvidence[0]!);
    const sensitivityEvidence = screen.getAllByTestId(
      "sensitivity-reference-evidence",
    );
    expect(
      within(sensitivityEvidence[0]!)
        .getAllByTestId("quantity")
        .map((node) => node.getAttribute("data-quantity-metric-id")),
    ).toEqual(["lower-support", "upper-support"]);
    expect(
      renderedQuantities.find(
        (node) =>
          node.getAttribute("data-quantity-metric-id") === "interval-reference",
      ),
    ).toHaveAccessibleName(/-0\.2.*0\.6/u);
    expect(
      renderedQuantities.find(
        (node) =>
          node.getAttribute("data-quantity-metric-id") === "unknown-reference",
      ),
    ).toHaveTextContent("Unknown");
    expect(screen.getAllByTestId("forest-reference-line")).toHaveLength(1);
    expect(screen.getAllByTestId("specification-reference-line")).toHaveLength(
      1,
    );
    expect(screen.getAllByTestId("sensitivity-reference-line")).toHaveLength(1);
    expect(
      screen.getByRole("img", { name: /100% above reference/u }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Bayesian Structural Time Series/u }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Difference-in-Differences/u }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Synthetic Control/u }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Factor Importance/u }),
    ).toBeInTheDocument();
  });

  it("keeps non-scalar forest direction neutral and provenance reachable", () => {
    renderWithProviders(
      <ForestPlot
        estimates={[
          {
            ci: { level: 0.95, lower: -0.2, upper: 0.6 },
            estimate: 0.1,
            id: "neutral-forest-estimate",
            label: "Neutral forest estimate",
          },
        ]}
        referenceValue={interval}
      />,
    );

    const chart = screen.getByRole("img", {
      name: /Forest plot with 1 studies/u,
    });
    expect(chart).not.toHaveAccessibleName(
      /positive effects|negative or null effects/u,
    );
    const evidence = screen.getByTestId("forest-reference-evidence");
    expect(chart).not.toContainElement(evidence);
    expect(
      within(evidence).getByRole("button", { name: /interval-reference/u }),
    ).toBeInTheDocument();
  });

  it("omits reference claims when a chart receives no producer value", () => {
    renderWithProviders(
      <div>
        <ForestPlot
          estimates={[
            {
              ci: { level: 0.95, lower: -0.2, upper: 0.6 },
              estimate: 0.1,
              id: "forest-estimate",
              label: "Forest estimate",
            },
          ]}
        />
        <SpecificationCurveChart
          specifications={[
            {
              ci: { level: 0.95, lower: -0.2, upper: 0.6 },
              estimate: 0.1,
              id: "specification-estimate",
            },
          ]}
        />
        <SensitivityPlot
          points={[{ gamma: 1, lowerBound: -0.2, upperBound: 0.6 }]}
        />
      </div>,
    );

    expect(
      screen.queryByTestId("forest-reference-line"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("specification-reference-line"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("sensitivity-reference-line"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/above reference/u)).not.toBeInTheDocument();
  });
});
