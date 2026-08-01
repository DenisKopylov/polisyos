import { render, screen } from "@testing-library/react";
import type {
  LegacyProvingGroundPayload,
  RunOperatorDiagnostic,
  RunOperatorProjectionStateLabel,
} from "@polisyos/runtime-api-client";

import {
  AuthorityBadge,
  createOpaqueAuthorityPresentation,
  createOperatorProjectionPresentation,
} from "../src/index";

const REJECTED_LABEL = {
  authority: "runtime_authority",
  label: "producer rejection",
  state: "rejected",
} satisfies RunOperatorProjectionStateLabel;

const DIAGNOSTIC = {
  authoritative_runtime_state: "blocked",
  blocker_overridable: false,
  downstream_impact: "Publication remains closed.",
  first_blocking_cause: "grounding_missing",
  next_diagnostic_command: "inspect grounding_missing",
  owner: "runtime-policy",
  phase: "grounding",
  projection_labels: [REJECTED_LABEL],
  projection_source: "governed_projection",
} satisfies RunOperatorDiagnostic;

describe("AuthorityBadge", () => {
  it("renders an opaque extension in neutral unknown posture", () => {
    render(
      <AuthorityBadge
        presentation={createOpaqueAuthorityPresentation(
          "producer_extension:novel",
        )}
      />,
    );

    const badge = screen.getByText("producer_extension:novel");
    expect(badge).toHaveAttribute("data-authority-recognition", "unrecognized");
    expect(badge).toHaveAttribute("data-presentation-tone", "neutral");
    expect(badge).not.toHaveAttribute("data-authority-grade");
  });

  it("rejects widened fixture provenance at runtime", () => {
    const widenedFixture: string =
      "fixture_only" satisfies LegacyProvingGroundPayload["fixture_authority"];

    expect(() => createOpaqueAuthorityPresentation(widenedFixture)).toThrow(
      /fixture provenance/i,
    );
  });

  it("derives known projection clothing from generated owner fields", () => {
    render(
      <AuthorityBadge
        presentation={createOperatorProjectionPresentation(
          DIAGNOSTIC,
          REJECTED_LABEL,
        )}
      />,
    );

    expect(screen.getByText("producer rejection")).toHaveAttribute(
      "data-presentation-tone",
      "fail",
    );
  });

  it("rejects cloned presentations and malformed fixture discriminators", () => {
    const issued = createOpaqueAuthorityPresentation("owner_extension");
    const forged = {
      ...issued,
      presentation: "recognized" as const,
      tone: "ok" as const,
    };
    const malformed = {
      authority: "fixture_only",
      label: "publishable",
      state: "publishable",
    } as unknown as RunOperatorProjectionStateLabel;
    const malformedOwner = {
      ...DIAGNOSTIC,
      projection_labels: [malformed],
    } as RunOperatorDiagnostic;

    expect(() => render(<AuthorityBadge presentation={forged} />)).toThrow(
      /owner-derived/i,
    );
    expect(() =>
      createOperatorProjectionPresentation(malformedOwner, malformed),
    ).toThrow(/fixture provenance/i);
  });

  it("rejects a generated-shaped label that is not owned by the diagnostic", () => {
    const fabricatedSibling = { ...REJECTED_LABEL };

    expect(() =>
      createOperatorProjectionPresentation(DIAGNOSTIC, fabricatedSibling),
    ).toThrow(/member of the generated owner diagnostic/i);
  });

  it("keeps runtime-widened projection extensions explicit and neutral", () => {
    const extension = {
      authority: "owner_extension",
      label: "novel projection label",
      state: "novel_state",
    } as unknown as RunOperatorProjectionStateLabel;
    const owner = {
      ...DIAGNOSTIC,
      projection_labels: [extension],
    } as RunOperatorDiagnostic;

    render(
      <AuthorityBadge
        presentation={createOperatorProjectionPresentation(owner, extension)}
      />,
    );

    const badge = screen.getByText("novel projection label");
    expect(badge).toHaveAttribute("data-authority-recognition", "unrecognized");
    expect(badge).toHaveAttribute("data-presentation-tone", "neutral");
    expect(badge).toHaveAttribute("data-owner-authority", "owner_extension");
    expect(badge).toHaveAttribute("data-authority-state", "novel_state");
  });

  it("does not expose caller-selected authority clothing", () => {
    const presentation = createOpaqueAuthorityPresentation("owner_extension");
    const compileOnly = () => (
      <>
        {/* @ts-expect-error Authority clothing cannot be supplied by class. */}
        <AuthorityBadge className="text-red-500" presentation={presentation} />
        {/* @ts-expect-error Authority clothing cannot be supplied by style. */}
        <AuthorityBadge presentation={presentation} style={{ color: "red" }} />
      </>
    );

    expect(compileOnly).toBeTypeOf("function");
  });
});
