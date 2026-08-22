import type { DepthNDomainRunProjection } from "@polisyos/runtime-api-client";

import { expectNoA11yViolations } from "@/test/a11y";
import { depthNDomainRunFixture } from "@/test/fixtures/depthNCycleBoard";

import { WeakestLinkExplainer } from "./WeakestLinkExplainer";

describe("WeakestLinkExplainer accessibility", () => {
  it("has no WCAG AA violations", async () => {
    const projection = depthNDomainRunFixture({
      design_problem_ref: "problem://housing-access",
      domain_role: "legal",
      evidence_class: "owner-recorded",
      evidence_witness: {},
      generation_cycle_run_id: "generation-cycle-42",
      terminal_distribution: {},
      weakest_links: [
        "Statute applicability remains unresolved",
        "The comparison population is incomplete",
      ],
    } satisfies Partial<DepthNDomainRunProjection>);

    await expectNoA11yViolations(
      <WeakestLinkExplainer projection={projection} />,
    );
  });
});
