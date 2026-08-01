import { render, screen, within } from "@testing-library/react";
import type { RunOperatorDiagnostic } from "@polisyos/runtime-api-client";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { OperatorDiagnosticPanel } from "./OperatorDiagnosticPanel";

const BLOCKED_DIAGNOSTIC = {
  authoritative_runtime_state: "blocked",
  blocker_overridable: false,
  downstream_impact: "Publication remains closed.",
  first_blocking_cause: "grounding_missing",
  next_diagnostic_command: "inspect grounding_missing",
  owner: "runtime-policy",
  phase: "grounding",
  projection_labels: [
    {
      authority: "runtime_authority",
      label: "publishable",
      state: "publishable",
    },
  ],
  projection_source: "governed_projection",
} satisfies RunOperatorDiagnostic;

describe("OperatorDiagnosticPanel", () => {
  it("never promotes projection labels when runtime authority is blocked", () => {
    render(
      <LocaleProvider>
        <OperatorDiagnosticPanel diagnostic={BLOCKED_DIAGNOSTIC} />
      </LocaleProvider>,
    );

    const panel = screen.getByTestId("operator-diagnostic-panel");
    expect(within(panel).getByText("blocked")).toHaveAttribute(
      "data-authority-recognition",
      "unrecognized",
    );
    const projectionLabel = within(panel).getByText("publishable");
    expect(projectionLabel).toHaveAttribute(
      "data-authority-recognition",
      "recognized",
    );
    expect(projectionLabel).toHaveAttribute(
      "data-presentation-tone",
      "neutral",
    );
    expect(projectionLabel).toHaveAttribute(
      "data-authority-state",
      "publishable",
    );
    expect(projectionLabel).toHaveAttribute(
      "data-owner-authority",
      "runtime_authority",
    );
    expect(projectionLabel).toHaveAttribute(
      "data-suppressed-by-blocker",
      "true",
    );
    const projectionSource = within(panel).getByText("governed_projection");
    expect(projectionSource).not.toHaveAttribute("data-authority-purpose");
    expect(projectionSource).toHaveAttribute(
      "data-projection-source",
      "governed_projection",
    );
    const projectionAuthority = within(panel).getByText("runtime authority");
    expect(projectionAuthority).not.toHaveAttribute("data-authority-purpose");
    expect(projectionAuthority).toHaveAttribute(
      "data-projection-authority",
      "runtime_authority",
    );
  });
});
