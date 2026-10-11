import {
  dedupeEvidenceArtifactRefs,
  evidenceArtifactRefKey,
  parseEvidenceFocus,
} from "./context";
import { buildEvidenceHref } from "./searchParams";
import { LEGACY_RUN_DETAIL_TAB_MAP } from "@/features/runs";

describe("evidence context helpers", () => {
  it("parses supported focus values", () => {
    expect(parseEvidenceFocus("plan")).toBe("plan");
    expect(parseEvidenceFocus("missing")).toBeNull();
  });

  it("deduplicates only refs with the same complete selected-view identity", () => {
    const profileA = `sha256:${"a".repeat(64)}`;
    const profileB = `sha256:${"b".repeat(64)}`;
    expect(
      dedupeEvidenceArtifactRefs([
        {
          artifact_id: "a1",
          kind: "fabric.data_snapshot",
          media_type: "application/json",
          manifest_profile_sha256: profileA,
        },
        {
          artifact_id: "a1",
          kind: "fabric.data_snapshot",
          media_type: "application/json",
          manifest_profile_sha256: profileA,
        },
        {
          artifact_id: "a1",
          kind: "fabric.data_snapshot",
          media_type: "application/json",
          manifest_profile_sha256: profileB,
        },
        {
          artifact_id: "a1",
          kind: "fabric.other_snapshot",
          media_type: "application/json",
          manifest_profile_sha256: profileA,
        },
        {
          artifact_id: "a1",
          kind: "fabric.data_snapshot",
          media_type: "text/plain",
          manifest_profile_sha256: profileA,
        },
        { artifact_id: "a2", kind: "evidence_bundle" },
      ]),
    ).toHaveLength(5);
    expect(
      evidenceArtifactRefKey({
        artifact_id: "a1",
        kind: "fabric.data_snapshot",
        media_type: "application/json",
        manifest_profile_sha256: profileA,
      }),
    ).not.toBe(
      evidenceArtifactRefKey({
        artifact_id: "a1",
        kind: "fabric.data_snapshot",
        media_type: "application/json",
        manifest_profile_sha256: profileB,
      }),
    );
    expect(
      evidenceArtifactRefKey({
        artifact_id: "a1",
        kind: "fabric.data_snapshot",
        media_type: "application/json",
        manifest_profile_sha256: profileA,
      }),
    ).not.toBe(
      evidenceArtifactRefKey({
        artifact_id: "a1",
        kind: "fabric.other_snapshot",
        media_type: "application/json",
        manifest_profile_sha256: profileA,
      }),
    );
  });

  it("builds profile-qualified evidence links and preserves legacy tab mapping", () => {
    const key = JSON.stringify([
      "a1",
      "fabric.data_snapshot",
      "application/json",
      `sha256:${"a".repeat(64)}`,
    ]);
    const href = buildEvidenceHref({
      runId: "run-1",
      focus: "artifact",
      artifactId: "a1",
      artifactRefKey: key,
    });
    const params = new URLSearchParams(href.split("?")[1]);
    expect(params.get("artifactId")).toBe("a1");
    expect(params.get("artifactRefKey")).toBe(key);
    expect(LEGACY_RUN_DETAIL_TAB_MAP.lineage).toBe("workflow");
  });
});
