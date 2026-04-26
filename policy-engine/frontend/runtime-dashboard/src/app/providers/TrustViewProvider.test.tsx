import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TrustViewProvider } from "./TrustViewProvider";
import { useTrustView } from "./useTrustView";

function Probe() {
  const { mode, setMode } = useTrustView();
  return (
    <div>
      <output aria-label="trust-mode">{mode}</output>
      <button type="button" onClick={() => setMode("compact")}>
        compact
      </button>
      <button type="button" onClick={() => setMode("expanded")}>
        expanded
      </button>
    </div>
  );
}

describe("TrustViewProvider", () => {
  it("reads URL state and persists mode changes to URL and preference", async () => {
    window.localStorage.clear();
    window.history.replaceState(null, "", "/runs/run_1?trust=expanded");

    render(
      <TrustViewProvider>
        <Probe />
      </TrustViewProvider>,
    );

    expect(screen.getByLabelText("trust-mode")).toHaveTextContent("expanded");
    expect(document.documentElement.dataset.trustView).toBe("expanded");

    await userEvent.click(screen.getByRole("button", { name: "compact" }));
    expect(screen.getByLabelText("trust-mode")).toHaveTextContent("compact");
    expect(window.location.search).toContain("trust=compact");
    expect(window.localStorage.getItem("polisyos.runtime.trust-view")).toBe(
      "compact",
    );
  });
});
