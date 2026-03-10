import { buildRuntimeApiUrl } from "@/api/url";
import type { SearchParamValue } from "@/lib/searchParams";

export function buildRuntimeStreamUrl(
  pathname: string,
  search?: Record<string, SearchParamValue>,
) {
  return buildRuntimeApiUrl(pathname, search);
}
