import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";

import type { AdmittedEpochStalenessProjection } from "@/features/runs/domain/epochStaleness";
import {
  epochProjection,
  epochStalenessAbsenceFixture,
  epochStalenessPositiveFixture,
} from "@/test/fixtures/epochStaleness";

import { EpochStalenessView } from "./EpochStalenessView";

function projection(candidate: Record<string, unknown>) {
  return epochProjection(
    candidate,
  ) as unknown as AdmittedEpochStalenessProjection;
}

describe.each([
  [
    "declared institutional and engineering absence",
    epochStalenessAbsenceFixture,
  ],
  ["content-bound positive fixture", epochStalenessPositiveFixture],
])("EpochStalenessView accessibility: %s", (_name, fixture) => {
  it("has no WCAG AA axe violations", async () => {
    const { container } = render(
      <EpochStalenessView
        projection={projection(fixture())}
        rawBytes={new TextEncoder().encode("{}")}
      />,
    );

    const result = await axe(container);
    expect(
      result.violations.map((violation) => ({
        id: violation.id,
        nodes: violation.nodes.map((node) => node.target),
      })),
    ).toEqual([]);
  });
});
