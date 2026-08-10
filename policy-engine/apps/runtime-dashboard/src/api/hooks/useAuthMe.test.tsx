import type { PropsWithChildren } from "react";
import { Suspense } from "react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { QueryClient } from "@tanstack/react-query";
import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";

import { queryKeys } from "@/api/queryKeys";
import { TEST_AUTH_ME } from "@/test/fixtures/authMe";
import { createTestQueryClient } from "@/test/queryClient";

const { authAwareRuntimeFetchMock } = vi.hoisted(() => ({
  authAwareRuntimeFetchMock: vi.fn(),
}));

vi.mock("@/api/url", () => ({
  buildRuntimeApiUrl: vi.fn(
    (pathname: string) => `http://localhost${pathname}`,
  ),
}));

vi.mock("@/app/auth/authSession", () => ({
  authAwareRuntimeFetch: (...args: unknown[]) =>
    authAwareRuntimeFetchMock(...args),
}));

import { authMeQueryOptions, useAuthMe, useSuspenseAuthMe } from "@/api/hooks/useAuthMe";

const TEST_SUPPORT_AUTH_SOURCES = [
  "src/api/hooks/useAuthMe.test.tsx",
  "src/test/render.tsx",
  "src/features/platform/routes/PlatformHealthPage.stories.tsx",
];

const productionFallbackImport =
  /import\s+(?:type\s+)?\{[^}]*\bFALLBACK_AUTH_ME\b[^}]*\}\s+from\s+["']@\/api\/hooks\/useAuthMe["']/;
const testOnlyFixtureImport =
  /import\s+\{\s*TEST_AUTH_ME\s*\}\s+from\s+["']@\/test\/fixtures\/authMe["']/;

function assertNoProductionFallbackImport(source: string): void {
  expect(source).not.toMatch(productionFallbackImport);
}

function createWrapper({
  client = createTestQueryClient(),
  suspense = false,
}: {
  client?: QueryClient;
  suspense?: boolean;
} = {}) {
  function Wrapper({ children }: PropsWithChildren) {
    const content = suspense ? (
      <Suspense fallback={<div>loading</div>}>{children}</Suspense>
    ) : (
      children
    );
    return <QueryClientProvider client={client}>{content}</QueryClientProvider>;
  }

  return Wrapper;
}

function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
    },
    status: 200,
    ...init,
  });
}

describe("useAuthMe", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    authAwareRuntimeFetchMock.mockReset();
  });

  it("test_support_never_imports_production_fallback_identity", () => {
    for (const sourcePath of TEST_SUPPORT_AUTH_SOURCES) {
      const source = readFileSync(resolve(process.cwd(), sourcePath), "utf8");
      assertNoProductionFallbackImport(source);
      expect(source).toMatch(testOnlyFixtureImport);
    }

    const fallbackName = ["FALLBACK", "AUTH", "ME"].join("_");
    expect(() =>
      assertNoProductionFallbackImport(
        `import { ${fallbackName} } from "@/api/hooks/useAuthMe";`,
      ),
    ).toThrow();
  });

  it("exposes a refetched identity query without a placeholder grant", () => {
    const options = authMeQueryOptions();

    expect(options.queryKey).toEqual(queryKeys.authMe());
    expect(options.placeholderData).toBeUndefined();
    expect(options.retry).toBe(false);
    expect(options.staleTime).toBe(0);
    expect(options.refetchOnMount).toBe("always");
  });

  it("loads the auth principal through the query function and regular hook", async () => {
    authAwareRuntimeFetchMock.mockResolvedValue(
      jsonResponse({
        ...TEST_AUTH_ME,
        display_name: "Trace Analyst",
      }),
    );

    const options = authMeQueryOptions();
    const queryFn = options.queryFn;
    expect(queryFn).toBeDefined();
    const payload = await queryFn!({} as never);
    expect(payload.display_name).toBe("Trace Analyst");
    expect(authAwareRuntimeFetchMock).toHaveBeenCalledWith(expect.any(Request));

    const client = createTestQueryClient();
    client.setQueryData(options.queryKey, payload);
    const view = renderHook(() => useAuthMe(), {
      wrapper: createWrapper({ client }),
    });

    expect(view.result.current.data?.display_name).toBe("Trace Analyst");
  });

  it("supports the suspense hook with prefetched auth data", () => {
    const client = createTestQueryClient();
    client.setQueryData(queryKeys.authMe(), TEST_AUTH_ME);

    const view = renderHook(() => useSuspenseAuthMe(), {
      wrapper: createWrapper({ client, suspense: true }),
    });

    expect(view.result.current.data.user_id).toBe(TEST_AUTH_ME.user_id);
  });

  it("surfaces api errors from the auth query function", async () => {
    authAwareRuntimeFetchMock.mockResolvedValue(
      new Response("denied", { status: 403 }),
    );

    const queryFn = authMeQueryOptions().queryFn;
    expect(queryFn).toBeDefined();
    await expect(queryFn!({} as never)).rejects.toThrow(
      "Failed to load auth principal",
    );
  });

  it("rejects a 401 identity response", async () => {
    authAwareRuntimeFetchMock.mockResolvedValue(
      jsonResponse({ detail: "unauthorized" }, { status: 401 }),
    );

    const queryFn = authMeQueryOptions().queryFn;
    expect(queryFn).toBeDefined();
    await expect(queryFn!({} as never)).rejects.toThrow("status=401");
  });

  it("rejects malformed identity JSON before it can become authority", async () => {
    authAwareRuntimeFetchMock.mockResolvedValue(
      jsonResponse({
        meta: TEST_AUTH_ME.meta,
        user_id: 42,
        tenant_id: "tenant-a",
      }),
    );

    const queryFn = authMeQueryOptions().queryFn;
    expect(queryFn).toBeDefined();
    await expect(queryFn!({} as never)).rejects.toThrow();
  });
});
