import { dedupeEvidenceArtifactRefs, parseEvidenceFocus } from "./context";
import { buildEvidenceHref, LEGACY_RUN_DETAIL_TAB_MAP } from "@/features/runs";

describe("evidence context helpers", () => {
  it("parses supported focus values", () => {
    expect(parseEvidenceFocus("plan")).toBe("plan");
    expect(parseEvidenceFocus("missing")).toBeNull();
  });

  it("deduplicates artifact refs by artifact id", () => {
    expect(
      dedupeEvidenceArtifactRefs([
        { artifact_id: "a1", kind: "decision_packet" },
        { artifact_id: "a1", kind: "decision_packet" },
        { artifact_id: "a2", kind: "evidence_bundle" },
      ]),
    ).toEqual([
      { artifact_id: "a1", kind: "decision_packet" },
      { artifact_id: "a2", kind: "evidence_bundle" },
    ]);
  });

  it("builds evidence deep links and preserves legacy tab mapping", () => {
    expect(buildEvidenceHref("run-1", "plan", { planId: "plan-1" })).toBe(
      "/evidence?runId=run-1&focus=plan&planId=plan-1",
    );
    expect(LEGACY_RUN_DETAIL_TAB_MAP.lineage).toBe("workflow");
  });
});
