import { useState, type PropsWithChildren } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { TrustViewToggle } from "./TrustViewToggle";
import {
  TrustViewBridgeProvider,
  type TrustViewMode,
} from "./TrustViewBridge";

function TestTrustViewProvider({ children }: PropsWithChildren) {
  const [mode, setMode] = useState<TrustViewMode>("off");
  return (
    <TrustViewBridgeProvider
      value={{
        closeInspector: () => undefined,
        cycleMode: () =>
          setMode((current) =>
            current === "off"
              ? "compact"
              : current === "compact"
                ? "expanded"
                : "off",
          ),
        density: "comfortable",
        inspectorSubject: null,
        mode,
        openInspector: () => undefined,
        setMode,
      }}
    >
      {children}
    </TrustViewBridgeProvider>
  );
}

describe("TrustViewToggle", () => {
  it("cycles off, compact and expanded modes", async () => {
    window.history.replaceState(null, "", "/runs/run_1");
    const user = userEvent.setup();

    render(
      <LocaleProvider>
        <TestTrustViewProvider>
          <TrustViewToggle />
        </TestTrustViewProvider>
      </LocaleProvider>,
    );

    expect(screen.getByRole("button")).toHaveAttribute("data-mode", "off");

    await user.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveAttribute("data-mode", "compact");

    await user.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveAttribute("data-mode", "expanded");
  });
});
