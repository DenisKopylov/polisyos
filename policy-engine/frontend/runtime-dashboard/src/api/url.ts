import { API_BASE_URL } from "@/lib/constants";
import { buildSearchParams, type SearchParamValue } from "@/lib/searchParams";

export function buildRuntimeApiUrl(
  pathname: string,
  search?: Record<string, SearchParamValue>,
) {
  const searchParams = buildSearchParams(search ?? {});
  const rawPath = API_BASE_URL
    ? new URL(pathname, API_BASE_URL).toString()
    : pathname;
  const url = new URL(rawPath, "http://localhost");

  for (const [key, value] of searchParams.entries()) {
    url.searchParams.set(key, value);
  }

  if (API_BASE_URL) {
    return url.toString();
  }

  const searchString = url.searchParams.toString();
  return searchString ? `${pathname}?${searchString}` : pathname;
}

export function buildRuntimeWebSocketUrl(
  pathname: string,
  search?: Record<string, SearchParamValue>,
) {
  const httpUrl = buildRuntimeApiUrl(pathname, search);
  const resolved = new URL(
    httpUrl,
    typeof window !== "undefined"
      ? window.location.href
      : "http://localhost",
  );
  resolved.protocol = resolved.protocol === "https:" ? "wss:" : "ws:";
  return resolved.toString();
}
