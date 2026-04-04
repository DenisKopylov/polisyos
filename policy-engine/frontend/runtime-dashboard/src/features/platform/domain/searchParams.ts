import { z } from "zod";

import {
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/lib/searchParams";

const platformSearchSchema = z.object({
  section: z
    .enum(["capabilities", "constraints", "health"])
    .optional()
    .catch(undefined),
});

export type PlatformSearchParams = z.infer<typeof platformSearchSchema>;

export function parsePlatformSearchParams(
  input: string | URLSearchParams | URL,
) {
  return parseSearchParamsWithSchema(platformSearchSchema, input);
}

export function buildPlatformHref(search?: Partial<PlatformSearchParams>) {
  return buildSearchHref("/platform", {
    section: search?.section,
  });
}
