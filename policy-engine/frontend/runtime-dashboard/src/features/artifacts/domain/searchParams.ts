import { z } from "zod";

import {
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/lib/searchParams";

export const ARTIFACT_TABS = ["content", "schema", "lineage"] as const;
export type ArtifactTab = (typeof ARTIFACT_TABS)[number];

const artifactSearchSchema = z.object({
  tab: z.enum(ARTIFACT_TABS).optional().catch(undefined),
});

export function parseArtifactSearchParams(
  input: string | URLSearchParams | URL,
): { tab: ArtifactTab } {
  const parsed = parseSearchParamsWithSchema(artifactSearchSchema, input);

  return {
    tab: parsed.tab ?? "content",
  };
}

export function buildArtifactHref(
  artifactId: string,
  search?: Partial<{ tab: ArtifactTab }>,
) {
  return buildSearchHref(`/artifacts/${artifactId}`, {
    tab: search?.tab ?? "content",
  });
}
