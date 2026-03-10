import { expectNoA11yViolations } from "@/test/a11y";

import LineageGraph from "./LineageGraph";

describe("LineageGraph accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <LineageGraph
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
