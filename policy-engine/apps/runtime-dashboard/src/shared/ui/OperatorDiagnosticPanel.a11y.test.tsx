import { within } from "@testing-library/react";
import type { RunOperatorDiagnostic } from "@polisyos/runtime-api-client";

import { expectNoA11yViolations } from "@/test/a11y";

import { OperatorDiagnosticPanel } from "./OperatorDiagnosticPanel";

describe("OperatorDiagnosticPanel accessibility", () => {
  it("exposes the real blocker structure and keyboard-readable evidence", async () => {
    const evidenceRef = "https://evidence.example/policy-grounding";
    const diagnostic = {
      authoritative_runtime_state: "blocked",
      authority_refs: { decision: "sha256:decision" },
      blocker_overridable: false,
      downstream_impact: "Publication remains closed.",
      evidence_refs: [evidenceRef],
      first_blocking_cause: "grounding_missing",
      next_diagnostic_command: "inspect grounding_missing",
      owner: "runtime-policy",
      phase: "grounding",
      projection_source: "governed_projection",
    } satisfies RunOperatorDiagnostic;

    const view = await expectNoA11yViolations(
      <OperatorDiagnosticPanel diagnostic={diagnostic} />,
    );

    expect(
      within(view.container).getByRole("heading", {
        name: "grounding_missing",
      }),
    ).toBeInTheDocument();
    expect(
      within(view.container).getByRole("link", { name: evidenceRef }),
    ).toHaveAttribute("href", evidenceRef);
    expect(
      within(view.container).getByRole("list", { name: "Evidence refs" }),
    ).toBeInTheDocument();
    expect(within(view.container).getByText("sha256:decision")).toBeVisible();
    expect(
      within(view.container).queryByRole("link", {
        name: /sha256:decision/,
      }),
    ).not.toBeInTheDocument();
  });

  it("keeps reference labels instance-scoped across multiple panels", async () => {
    const diagnostic = {
      authoritative_runtime_state: "blocked",
      authority_refs: { decision: "sha256:decision" },
      blocker_overridable: false,
      downstream_impact: "Publication remains closed.",
      evidence_refs: ["https://evidence.example/policy-grounding"],
      first_blocking_cause: "grounding_missing",
      next_diagnostic_command: "inspect grounding_missing",
      owner: "runtime-policy",
      phase: "grounding",
      projection_source: "governed_projection",
    } satisfies RunOperatorDiagnostic;

    const view = await expectNoA11yViolations(
      <>
        <OperatorDiagnosticPanel diagnostic={diagnostic} />
        <OperatorDiagnosticPanel diagnostic={diagnostic} />
      </>,
    );
    const panels = within(view.container).getAllByTestId(
      "operator-diagnostic-panel",
    );
    const labelIds = panels.map((panel) => {
      const label = within(panel).getByText("Authority refs");
      const list = within(panel).getByRole("list", { name: "Authority refs" });
      expect(list).toHaveAttribute("aria-labelledby", label.id);
      return label.id;
    });

    expect(new Set(labelIds).size).toBe(panels.length);
  });
});
