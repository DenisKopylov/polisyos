import { runPaperPacketFixture } from "@/test/fixtures/runPaper";

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
});
