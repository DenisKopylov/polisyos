import { z } from "zod";

import {
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/lib/searchParams";

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
  focus: evidenceFocusSchema.optional().catch(undefined),
  needId: z.string().trim().min(1).optional().catch(undefined),
  planId: z.string().trim().min(1).optional().catch(undefined),
  promotionId: z.string().trim().min(1).optional().catch(undefined),
  runId: z.string().trim().min(1).optional().catch(undefined),
  surface: evidenceSurfaceSchema.optional().catch(undefined),
});

export type EvidenceSearchParams = z.infer<typeof evidenceSearchSchema>;

export function parseEvidenceSearchParams(
  input: string | URLSearchParams | URL,
) {
  return parseSearchParamsWithSchema(evidenceSearchSchema, input);
}

export function buildEvidenceHref(search?: Partial<EvidenceSearchParams>) {
  return buildSearchHref("/evidence", {
    artifactId: search?.artifactId,
    focus: search?.focus,
    needId: search?.needId,
    planId: search?.planId,
    promotionId: search?.promotionId,
    runId: search?.runId,
    surface: search?.surface,
  });
}
