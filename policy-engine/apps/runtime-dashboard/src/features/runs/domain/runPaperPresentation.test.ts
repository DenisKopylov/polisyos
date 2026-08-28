import {
  authorityAbstainingRunPaperPacketFixture,
  runPaperPacketFixture,
} from "@/test/fixtures/runPaper";

import {
  buildRunPaperSemanticRoster,
  presentRunPaper,
} from "./runPaperPresentation";

describe("run paper presentation", () => {
  it("preserves producer facts and the typed unavailable case without defaults", () => {
    const packet = runPaperPacketFixture({ artifact_links: [] });
    const presentation = presentRunPaper(packet);

    expect(presentation.run).toEqual(packet.run);
    expect(presentation.source).toEqual(packet.source);
    expect(presentation.stageTrace).toEqual(packet.stage_trace);
    expect(presentation.artifactLinks).toEqual([]);
    expect(presentation.caseRecord).toEqual({
      availability: "artifact_missing",
      capability_state: "producer_missing",
      closure_signal: "case-record-not-run-bound",
      may_not_use_for: [
        "case_identity",
        "design_record",
        "grounding_state",
        "admission_state",
        "promotion_state",
        "blockers",
        "limitations",
        "objections",
        "abstentions",
      ],
      owner_route: "team-runtime",
      reason_code: "case-record-not-run-bound",
    });
    expect(JSON.stringify(presentation)).not.toMatch(
      /false|placeholder|N\/A/iu,
    );
    const roster = buildRunPaperSemanticRoster(presentation);
    expect(roster).toContainEqual({
      kind: "array",
      length: 0,
      path: "/artifactLinks",
    });
    expect(roster).toContainEqual({
      kind: "null",
      path: "/source/environment",
    });
    expect(new Set(roster.map((node) => node.path)).size).toBe(roster.length);
  });

  it("preserves every authority-abstaining record fact in the semantic roster", () => {
    const packet = authorityAbstainingRunPaperPacketFixture();
    const presentation = presentRunPaper(packet);
    const roster = buildRunPaperSemanticRoster(presentation);

    expect(presentation.caseRecord).toEqual(packet.case_record);
    for (const [role, authority] of [
      ["grounding", "generation_cycle_grounding_authority"],
      ["admission", "hypothesis_ledger_admission_authority"],
      ["promotion", "layer3_g4_promotion_authority"],
    ] as const) {
      expect(roster).toContainEqual({
        kind: "string",
        path: `/caseRecord/${role}_nonreceipt/missing_authority`,
        value: authority,
      });
    }
    expect(roster).toContainEqual({
      kind: "string",
      path: "/caseRecord/grounding_nonreceipt/denied_uses/1",
      value: "grounded_case_projection",
    });
    expect(roster).toContainEqual({
      kind: "string",
      path: "/caseRecord/admission_nonreceipt/denied_uses/1",
      value: "admitted_case_projection",
    });
    expect(roster).toContainEqual({
      kind: "string",
      path: "/caseRecord/promotion_nonreceipt/denied_uses/1",
      value: "governed_case_projection",
    });
  });
});
