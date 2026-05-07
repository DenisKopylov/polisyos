function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
    },
    status: 200,
    ...init,
  });
}

describe("auth session", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("VITE_AUTH_REFRESH_URL", "/api/v1/auth/refresh");
    window.__RUNTIME_DASHBOARD_TEST__ = true;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("deduplicates concurrent refresh attempts", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ access_token: "token-123" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { readAuthSessionState, refreshAuthSession } =
      await import("@/app/auth/authSession");

    const [first, second] = await Promise.all([
      refreshAuthSession({ reason: "manual" }),
      refreshAuthSession({ reason: "manual" }),
    ]);

    expect(first).toBe("token-123");
    expect(second).toBe("token-123");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(readAuthSessionState()).toMatchObject({
      accessToken: "token-123",
      status: "authenticated",
    });
  });

  it("replays one failed request after a successful refresh", async () => {
    const fetchMock = vi
      .fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: "token-456" }, { status: 200 }),
      )
      .mockResolvedValueOnce(jsonResponse({ ok: true }, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { authAwareRuntimeFetch } = await import("@/app/auth/authSession");
    const response = await authAwareRuntimeFetch(
      new Request("https://dashboard.example/api/v1/runs", {
        method: "GET",
      }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(3);

    const replayRequest = fetchMock.mock.calls[2]?.[0] as Request;
    expect(replayRequest.headers.get("authorization")).toBe("Bearer token-456");
    expect(replayRequest.headers.get("x-runtime-dashboard-replay")).toBe("1");
  });
});
