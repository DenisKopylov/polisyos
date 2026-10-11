import { z } from "zod";

import {
  getSearchParams,
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/shared/lib/searchParams";
import { parseEvidenceArtifactRefKey } from "@/shared/lib/domain/evidence";

const evidenceFocusSchema = z.enum([
  "overview",
  "need",
  "plan",
  "promotion",
  "artifact",
]);

const evidenceSurfaceSchema = z.enum(["freshness-braid", "connector-cards"]);

const evidenceSearchSchema = z.object({
  artifactId: z.string().trim().min(1).optional().catch(undefined),
  artifactRefKey: z.string().trim().min(1).optional().catch(undefined),
  capability: z.string().trim().min(1).optional().catch(undefined),
  focus: evidenceFocusSchema.optional().catch(undefined),
  needId: z.string().trim().min(1).optional().catch(undefined),
  planId: z.string().trim().min(1).optional().catch(undefined),
  promotionId: z.string().trim().min(1).optional().catch(undefined),
  runId: z.string().trim().min(1).optional().catch(undefined),
  surface: evidenceSurfaceSchema.optional().catch(undefined),
});

export type EvidenceSearchParams = z.infer<typeof evidenceSearchSchema>;

export type ParsedEvidenceSearchParams = EvidenceSearchParams & {
  artifactRefKeyInvalid: boolean;
};

export function parseEvidenceSearchParams(
  input: string | URLSearchParams | URL,
): ParsedEvidenceSearchParams {
  const params = getSearchParams(input);
  const refs = params.getAll("artifactRefKey");
  const parsed = parseSearchParamsWithSchema(evidenceSearchSchema, params);
  const invalid =
    refs.length > 1 ||
    (refs.length === 1 &&
      (parsed.artifactRefKey !== refs[0] ||
        parseEvidenceArtifactRefKey(refs[0] ?? "") === null));
  return {
    ...parsed,
    artifactRefKey: invalid ? undefined : parsed.artifactRefKey,
    artifactRefKeyInvalid: invalid,
  };
}

export function buildEvidenceHref(search?: Partial<EvidenceSearchParams>) {
  return buildSearchHref("/evidence", {
    artifactId: search?.artifactId,
    artifactRefKey: search?.artifactRefKey,
    capability: search?.capability,
    focus: search?.focus,
    needId: search?.needId,
    planId: search?.planId,
    promotionId: search?.promotionId,
    runId: search?.runId,
    surface: search?.surface,
  });
}
