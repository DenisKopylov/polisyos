import { expectNoA11yViolations } from "@/test/a11y";

import { TrustViewBridgeProvider, useTrustView } from "./TrustViewBridge";

function TrustViewModeProbe() {
  const { mode } = useTrustView();
  return <output aria-label="Trust View mode">{mode}</output>;
}

describe("TrustViewBridge accessibility", () => {
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
        <TrustViewModeProbe />
      </TrustViewBridgeProvider>,
    );
  });
});
