import { expectNoA11yViolations } from "@/test/a11y";

import { TrustInspector } from "./TrustInspector";
import { TrustViewBridgeProvider } from "./TrustViewBridge";

describe("TrustInspector accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <TrustViewBridgeProvider
        value={{
          closeInspector: () => undefined,
          cycleMode: () => undefined,
          density: "comfortable",
          inspectorSubject: {
            id: "lineage-1",
            kind: "lineage",
            label: "Decision evidence",
            trustMetadata: {
              dispute_status: "none",
              freshness: "current",
              verification_status: "verified",
              verified_by: "runtime-verifier",
            },
          },
          mode: "expanded",
          openInspector: () => undefined,
          setMode: () => undefined,
        }}
      >
        <TrustInspector />
      </TrustViewBridgeProvider>,
    );
  });
});
