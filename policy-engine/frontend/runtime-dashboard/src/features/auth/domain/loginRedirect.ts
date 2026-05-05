import { LOGIN_PATH, LOGIN_URL } from "@/shared/lib/constants";

export type LoginNavigationMode = "document" | "spa";

export type LoginNavigationTarget = {
  href: string;
  mode: LoginNavigationMode;
  usesDedicatedLogin: boolean;
};

function normalizeNextPath(nextPath: string): string {
  const trimmed = nextPath.trim();
  return trimmed.length > 0 ? trimmed : "/";
}

export function buildLoginNavigationTarget(
  nextPath: string,
  loginUrl = LOGIN_URL,
  loginPath = LOGIN_PATH,
): LoginNavigationTarget {
  const normalizedNext = normalizeNextPath(nextPath);

  if (loginUrl === loginPath) {
    const params = new URLSearchParams({ next: normalizedNext });
    return {
      href: `${loginPath}?${params.toString()}`,
      mode: "spa",
      usesDedicatedLogin: false,
    };
  }

  if (loginUrl.startsWith("/")) {
    const params = new URLSearchParams({ next: normalizedNext });
    return {
      href: `${loginUrl}?${params.toString()}`,
      mode: "document",
      usesDedicatedLogin: true,
    };
  }

  const url = new URL(loginUrl);
  url.searchParams.set("next", normalizedNext);
  return {
    href: url.toString(),
    mode: "document",
    usesDedicatedLogin: true,
  };
}
