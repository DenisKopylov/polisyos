import { expectNoA11yViolations } from "@/test/a11y";

import { AuthoredText } from "./AuthoredText";
import { AuthorshipProvider, AuthorshipTimeline } from "./AuthorshipProvider";

describe("AuthoredText accessibility", () => {
  it("has no detectable accessibility violations across all five authorship registers", async () => {
    await expectNoA11yViolations(
      <AuthorshipProvider highlightMode="prominent">
        <div className="gap-4 xl:grid xl:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="space-y-4">
            <AuthoredText
              author="citation"
              sourceHref="/evidence?focus=artifact&artifactId=eb_17&runId=run-42"
              sourceRef="Evidence bundle EB-17"
              timestamp="2026-04-22T10:32:00Z"
            >
              Section 12 requires the baseline threshold to be published.
            </AuthoredText>
            <AuthoredText author="human" timestamp="2026-04-22T10:33:00Z">
              Operator validated the rollout window.
            </AuthoredText>
            <AuthoredText author="drafter" timestamp="2026-04-22T10:34:00Z">
              Drafter summarized the policy trade-off in one paragraph.
            </AuthoredText>
            <AuthoredText author="formalizer" timestamp="2026-04-22T10:35:00Z">
              Formalizer aligned the language to the ratification template.
            </AuthoredText>
            <AuthoredText author="critic" timestamp="2026-04-22T10:36:00Z">
              Critic flagged the remaining uncertainty envelope.
            </AuthoredText>
          </div>
          <AuthorshipTimeline />
        </div>
      </AuthorshipProvider>,
    );
  });
});
