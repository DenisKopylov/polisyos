import { z } from "zod";

import {
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/shared/lib/searchParams";

const lexSearchSchema = z.object({
  outputDir: z.string().trim().min(1).optional().catch(undefined),
  pipelineId: z.string().trim().min(1).optional().catch(undefined),
  q: z.string().trim().min(1).optional().catch(undefined),
  resume: z.coerce.boolean().optional().catch(undefined),
});

export type LexSearchParams = z.infer<typeof lexSearchSchema>;

export function parseLexSearchParams(input: string | URLSearchParams | URL) {
  return parseSearchParamsWithSchema(lexSearchSchema, input);
}

export function buildLexHref(search?: Partial<LexSearchParams>) {
  return buildSearchHref("/knowledge", {
    outputDir: search?.outputDir,
    pipelineId: search?.pipelineId,
    q: search?.q,
    resume: search?.resume,
  });
}
