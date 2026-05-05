import { z } from "zod";

import {
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/shared/lib/searchParams";

export const COMPOSER_MODES = ["workflow", "nl"] as const;
export type ComposerMode = (typeof COMPOSER_MODES)[number];

const composerSearchSchema = z.object({
  fromRun: z.string().trim().min(1).optional().catch(undefined),
  mode: z.enum(COMPOSER_MODES).optional().catch(undefined),
});

export type ComposerSearchParams = {
  fromRun: string | null;
  mode: ComposerMode | null;
};

export function parseComposerSearchParams(
  input: string | URLSearchParams | URL,
): ComposerSearchParams {
  const parsed = parseSearchParamsWithSchema(composerSearchSchema, input);

  return {
    fromRun: parsed.fromRun ?? null,
    mode: parsed.mode ?? null,
  };
}

export function buildComposerHref(search?: Partial<ComposerSearchParams>) {
  return buildSearchHref("/compose", {
    fromRun: search?.fromRun ?? null,
    mode: search?.mode ?? null,
  });
}
