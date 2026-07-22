import type { DecisionPacketAuthoredBlock } from "@polisyos/runtime-api-client";

import { expectNoA11yViolations } from "@/test/a11y";

import { CandidateFrame } from "./CandidateFrame";

describe("CandidateFrame accessibility", () => {
  it("has no WCAG AA violations", async () => {
    const block = {
      author: "critic",
      content: "The proposed threshold still requires governed verification.",
      sources: [{ href: "/artifacts/evidence-7", ref: "evidence-7" }],
    } satisfies DecisionPacketAuthoredBlock;

    await expectNoA11yViolations(
      <CandidateFrame
        authorityPurpose={["operator_review"]}
        block={block}
        mayNotUseFor={["publication"]}
        title="Candidate recommendation"
      />,
    );
  });
});
