import type { DepthNDomainRunProjection } from "@polisyos/runtime-api-client";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";
import { depthNDomainRunFixture } from "@/test/fixtures/depthNCycleBoard";

import { WeakestLinkExplainer } from "./WeakestLinkExplainer";

describe("WeakestLinkExplainer", () => {
  it("uses the producer supplied weakest link without recomputing it", () => {
    const projection = depthNDomainRunFixture({
      design_problem_ref: "problem://housing-access",
      domain_role: "legal",
      evidence_class: "strong",
      evidence_witness: { status: "verified" },
      generation_cycle_run_id: "generation-cycle-42",
      terminal_distribution: { blocked: 0.99 },
      weakest_links: ["Producer: statute applicability remains unresolved"],
    } satisfies Partial<DepthNDomainRunProjection>);

    renderWithProviders(<WeakestLinkExplainer projection={projection} />);

    expect(screen.getByText(projection.weakest_links[0])).toBeInTheDocument();
    expect(screen.getByTestId("weakest-link-explainer")).toHaveAttribute(
      "data-weakest-link-source",
      "producer",
    );
    expect(screen.queryByText("blocked")).not.toBeInTheDocument();
    expect(screen.queryByText("verified")).not.toBeInTheDocument();
  });
});
