import { z } from "zod";

import {
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/shared/lib/searchParams";
import {
  evidenceArtifactRefKey,
  parseEvidenceArtifactRefKey,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";

export const ARTIFACT_TABS = ["content", "schema", "lineage"] as const;
export type ArtifactTab = (typeof ARTIFACT_TABS)[number];
export const ARTIFACT_VIEWS = ["default", "reading"] as const;
export type ArtifactView = (typeof ARTIFACT_VIEWS)[number];

const artifactSearchSchema = z.object({
  tab: z.enum(ARTIFACT_TABS).optional().catch(undefined),
  view: z.enum(ARTIFACT_VIEWS).optional().catch(undefined),
});

const MANIFEST_PROFILE_SHA256 = /^sha256:[0-9a-f]{64}$/u;

export type ManifestProfileSelection =
  | Readonly<{ kind: "unqualified" }>
  | Readonly<{ kind: "selected"; value: string }>
  | Readonly<{ kind: "invalid" }>;

export type ArtifactReferenceSelection =
  | Readonly<{ kind: "unqualified"; ref: EvidenceArtifactRef }>
  | Readonly<{ kind: "selected"; ref: EvidenceArtifactRef }>
  | Readonly<{ kind: "invalid" }>;

export function parseManifestProfileSelection(
  params: URLSearchParams,
): ManifestProfileSelection {
  const values = params.getAll("manifest_profile_sha256");
  if (values.length === 0) {
    return { kind: "unqualified" };
  }
  const [value] = values;
  if (
    values.length !== 1 ||
    value === undefined ||
    !MANIFEST_PROFILE_SHA256.test(value)
  ) {
    return { kind: "invalid" };
  }
  return { kind: "selected", value };
}

export function parseArtifactReferenceSelection(
  params: URLSearchParams,
  artifactId: string | undefined,
): ArtifactReferenceSelection {
  if (!artifactId) {
    return { kind: "invalid" };
  }
  const profile = parseManifestProfileSelection(params);
  if (profile.kind === "invalid") {
    return { kind: "invalid" };
  }
  const keys = params.getAll("artifactRefKey");
  if (keys.length > 1) {
    return { kind: "invalid" };
  }
  const [key] = keys;
  if (key === undefined) {
    return profile.kind === "selected"
      ? {
          kind: "selected",
          ref: {
            artifact_id: artifactId,
            manifest_profile_sha256: profile.value,
          },
        }
      : { kind: "unqualified", ref: { artifact_id: artifactId } };
  }

  const ref = parseEvidenceArtifactRefKey(key);
  if (
    ref === null ||
    ref.artifact_id !== artifactId ||
    (profile.kind === "selected" &&
      ref.manifest_profile_sha256 !== profile.value)
  ) {
    return { kind: "invalid" };
  }
  return { kind: "selected", ref };
}

export function parseArtifactSearchParams(
  input: string | URLSearchParams | URL,
): { tab: ArtifactTab; view: ArtifactView } {
  const parsed = parseSearchParamsWithSchema(artifactSearchSchema, input);

  return {
    tab: parsed.tab ?? "content",
    view: parsed.view ?? "default",
  };
}

export function buildArtifactHref(
  artifactId: string,
  search?: Partial<{
    tab: ArtifactTab;
    view: ArtifactView;
    manifestProfileSha256: string | null;
    artifactRef: EvidenceArtifactRef;
  }>,
) {
  const href = buildSearchHref("/artifacts/" + artifactId, {
    tab: search?.tab ?? "content",
    view: search?.view === "reading" ? "reading" : undefined,
  });
  if (search?.artifactRef) {
    const refKey = evidenceArtifactRefKey(search.artifactRef);
    if (
      search.artifactRef.artifact_id !== artifactId ||
      parseEvidenceArtifactRefKey(refKey) === null
    ) {
      throw new Error("artifact href does not match a valid typed ref");
    }
    const selectedProfile = search.artifactRef.manifest_profile_sha256 ?? null;
    if (
      search.manifestProfileSha256 !== undefined &&
      search.manifestProfileSha256 !== selectedProfile
    ) {
      throw new Error(
        "artifact href profile selector disagrees with its typed ref",
      );
    }
    const url = new URL(href, "http://localhost");
    url.searchParams.set("artifactRefKey", refKey);
    return url.pathname + "?" + url.searchParams.toString();
  }
  const profile = search?.manifestProfileSha256;
  if (profile === undefined || profile === null) {
    return href;
  }
  if (!MANIFEST_PROFILE_SHA256.test(profile)) {
    throw new Error("artifact href profile selector is malformed");
  }
  const url = new URL(href, "http://localhost");
  url.searchParams.set("manifest_profile_sha256", profile);
  return url.pathname + "?" + url.searchParams.toString();
}
