import type { PolicyDesignCaseProjectionBlocker } from "@polisyos/runtime-api-client";

import { expectNoA11yViolations } from "@/test/a11y";

import { BlockerCard } from "./BlockerCard";

describe("BlockerCard accessibility", () => {
  it("has no WCAG AA violations", async () => {
    const blocker = {
      code: "missing_grounded_effect",
      evidence_ref: "/artifacts/evidence-7",
      message: "No grounded effect supports the publication claim.",
      module_id: "runtime-quality",
      next_action: "Attach a verified effect artifact.",
      owner: "effect-grounding",
      severity: "blocking",
    } satisfies PolicyDesignCaseProjectionBlocker;

    await expectNoA11yViolations(<BlockerCard blocker={blocker} />);
  });
});
