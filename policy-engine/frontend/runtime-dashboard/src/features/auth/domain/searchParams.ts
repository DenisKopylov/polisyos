import { z } from "zod";

import {
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/lib/searchParams";

const loginSearchSchema = z.object({
  next: z.string().trim().min(1).optional().catch(undefined),
});

export type LoginSearchParams = z.infer<typeof loginSearchSchema> & {
  next: string;
};

export function parseLoginSearchParams(
  input: string | URLSearchParams | URL,
): LoginSearchParams {
  const parsed = parseSearchParamsWithSchema(loginSearchSchema, input);
  return {
    next:
      parsed.next &&
      parsed.next.startsWith("/") &&
      !parsed.next.startsWith("//")
        ? parsed.next
        : "/",
  };
}

export function buildLoginHref(search?: Partial<LoginSearchParams>) {
  return buildSearchHref("/login", {
    next: search?.next ?? "/",
  });
}
