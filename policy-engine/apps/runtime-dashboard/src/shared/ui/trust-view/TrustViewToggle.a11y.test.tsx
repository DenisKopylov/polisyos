import { expectNoA11yViolations } from "@/test/a11y";

import { TrustViewBridgeProvider } from "./TrustViewBridge";
import { TrustViewToggle } from "./TrustViewToggle";

describe("TrustViewToggle accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <TrustViewBridgeProvider
        value={{
          closeInspector: () => undefined,
          cycleMode: () => undefined,
          density: "comfortable",
          inspectorSubject: null,
          mode: "compact",
          openInspector: () => undefined,
          setMode: () => undefined,
        }}
      >
        <TrustViewToggle />
      </TrustViewBridgeProvider>,
    );
  });
});
