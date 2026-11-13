import { expectNoA11yViolations } from "@/test/a11y";
import {
  evidenceArtifactRefKey,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";

import LineageGraph from "./LineageGraph";

function artifactHrefFor(ref: EvidenceArtifactRef): string {
  const query = new URLSearchParams({
    tab: "content",
    artifactRefKey: evidenceArtifactRefKey(ref),
  });
  return `/artifacts/${ref.artifact_id}?${query.toString()}`;
}

describe("LineageGraph accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <LineageGraph
        artifactHrefFor={artifactHrefFor}
        nodes={[
          {
            artifact_id: "artifact-root",
            depth: 0,
            kind: "decision_packet",
            status: "ok",
          },
          {
            artifact_id: "artifact-child",
            depth: 1,
            kind: "evidence_bundle",
            status: "partial",
          },
        ]}
        edges={[
          {
            parent_artifact_id: "artifact-root",
            child_artifact_id: "artifact-child",
            role: "derived_from",
          },
        ]}
        rootArtifactIds={["artifact-root"]}
      />,
    );
  });
});
