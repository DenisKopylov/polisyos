import type { SelectedArtifactRef } from "./quantity.types";
import { coreArtifactRefSchema } from "@/api/validators";

export type SelectedArtifactRefProjection =
  | { status: "absent" }
  | { status: "profileless" }
  | { status: "malformed" }
  | { status: "candidate"; selectedArtifactRef: SelectedArtifactRef };

/**
 * Project a supplied reference into its profile-selected wire shape.
 *
 * A candidate here is only a well-shaped tuple; this function does not verify
 * artifact existence, profile binding, currentness, provenance, or admission.
 */
export function projectSelectedArtifactRef(
  value: unknown,
): SelectedArtifactRefProjection {
  if (value === undefined || value === null) return { status: "absent" };
  const parsed = coreArtifactRefSchema.safeParse(value);
  if (!parsed.success) return { status: "malformed" };

  const profile = parsed.data.manifest_profile_sha256;
  if (profile === undefined || profile === null) {
    return { status: "profileless" };
  }

  return {
    status: "candidate",
    selectedArtifactRef: {
      artifact_id: parsed.data.artifact_id,
      kind: parsed.data.kind,
      media_type: parsed.data.media_type,
      manifest_profile_sha256: profile,
    },
  };
}
