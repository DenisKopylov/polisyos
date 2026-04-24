import { z } from "zod";

import {
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/lib/searchParams";

export const ARTIFACT_TABS = ["content", "schema", "lineage"] as const;
export type ArtifactTab = (typeof ARTIFACT_TABS)[number];
export const ARTIFACT_VIEWS = ["default", "reading"] as const;
export type ArtifactView = (typeof ARTIFACT_VIEWS)[number];

const artifactSearchSchema = z.object({
  tab: z.enum(ARTIFACT_TABS).optional().catch(undefined),
  view: z.enum(ARTIFACT_VIEWS).optional().catch(undefined),
});

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
  search?: Partial<{ tab: ArtifactTab; view: ArtifactView }>,
) {
  return buildSearchHref(`/artifacts/${artifactId}`, {
    tab: search?.tab ?? "content",
    view: search?.view === "reading" ? "reading" : undefined,
  });
}
