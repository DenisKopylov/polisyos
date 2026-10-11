import { describe, expect, it } from "vitest";

import {
  buildArtifactHref,
  parseArtifactReferenceSelection,
} from "./searchParams";
import { evidenceArtifactRefKey } from "@/shared/lib/domain/evidence";

const profileA = "sha256:" + "a".repeat(64);
const profileB = "sha256:" + "b".repeat(64);

describe("artifact view selection", () => {
  it("keeps same-blob sibling profiles independently addressable", () => {
    const first = {
      artifact_id: "artifact-shared",
      kind: "decision_packet.v1",
      media_type: "application/json",
      manifest_profile_sha256: profileA,
    };
    const second = {
      ...first,
      kind: "decision_packet.v2",
      manifest_profile_sha256: profileB,
    };
    const firstHref = buildArtifactHref(first.artifact_id, {
      tab: "lineage",
      artifactRef: first,
    });
    const secondHref = buildArtifactHref(second.artifact_id, {
      tab: "lineage",
      artifactRef: second,
    });

    expect(firstHref).not.toBe(secondHref);
    expect(
      parseArtifactReferenceSelection(
        new URLSearchParams(firstHref.split("?")[1]),
        first.artifact_id,
      ),
    ).toEqual({ kind: "selected", ref: first });
    expect(
      parseArtifactReferenceSelection(
        new URLSearchParams(secondHref.split("?")[1]),
        second.artifact_id,
      ),
    ).toEqual({ kind: "selected", ref: second });
    expect(evidenceArtifactRefKey(first)).not.toBe(
      evidenceArtifactRefKey(second),
    );
  });

  it("rejects repeated or contradictory profile selectors", () => {
    const ref = {
      artifact_id: "artifact-shared",
      kind: "decision_packet.v1",
      media_type: "application/json",
      manifest_profile_sha256: profileA,
    };
    expect(() =>
      buildArtifactHref(ref.artifact_id, {
        artifactRef: ref,
        manifestProfileSha256: profileB,
      }),
    ).toThrow("disagrees");

    const duplicate = new URLSearchParams();
    duplicate.append("manifest_profile_sha256", profileA);
    duplicate.append("manifest_profile_sha256", profileA);
    expect(parseArtifactReferenceSelection(duplicate, ref.artifact_id)).toEqual(
      { kind: "invalid" },
    );
  });
});
