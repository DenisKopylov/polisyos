import type { ZodType } from "zod";

export type SearchParamInput = string | URLSearchParams | URL;
export type SearchParamValue =
  | string
  | number
  | boolean
  | null
  | undefined;

export function getSearchParams(input: SearchParamInput) {
  if (typeof input === "string") {
    return new URL(input, "http://localhost").searchParams;
  }
  if (input instanceof URL) {
    return input.searchParams;
  }
  return input;
}

export function normalizeSearchParamRecord(searchParams: URLSearchParams) {
  const record = Object.fromEntries(searchParams.entries());
  return Object.fromEntries(
    Object.entries(record).map(([key, value]) => [
      key,
      value.trim() || undefined,
    ]),
  );
}

export function parseSearchParamsWithSchema<TSchema extends ZodType>(
  schema: TSchema,
  input: SearchParamInput,
) {
  return schema.parse(normalizeSearchParamRecord(getSearchParams(input)));
}

export function buildSearchParams(
  values: Record<string, SearchParamValue>,
): URLSearchParams {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(values)) {
    if (value == null) {
      continue;
    }
    if (typeof value === "string" && value.trim() === "") {
      continue;
    }
    searchParams.set(key, String(value));
  }

  return searchParams;
}

export function buildSearchHref(
  pathname: string,
  values?: Record<string, SearchParamValue>,
) {
  const searchParams = buildSearchParams(values ?? {});
  const search = searchParams.toString();
  return search ? `${pathname}?${search}` : pathname;
}
