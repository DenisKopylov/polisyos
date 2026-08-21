import { NavigationRoute, registerRoute } from "workbox-routing";
import { createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { clientMatchAll, clientPostMessage, navigationHandler } = vi.hoisted(() => {
  const clientPostMessage = vi.fn();

  return {
    clientMatchAll: vi.fn(async () => [{ postMessage: clientPostMessage }]),
    clientPostMessage,
    navigationHandler: vi.fn(async () => new Response("navigation shell")),
  };
});

vi.mock("workbox-core", () => ({ clientsClaim: vi.fn() }));

vi.mock("workbox-precaching", () => ({
  cleanupOutdatedCaches: vi.fn(),
  createHandlerBoundToURL: vi.fn(() => navigationHandler),
  precacheAndRoute: vi.fn(),
}));

vi.mock("workbox-routing", async (importOriginal) => {
  const workboxRouting = await importOriginal<typeof import("workbox-routing")>();

  return { ...workboxRouting, registerRoute: vi.fn() };
});

type WorkerEventListener = (event: Event) => void;

const registeredWorkerEvents = new Map<string, WorkerEventListener>();
const staticManifest = [{ revision: "r3", url: "/assets/app-r3.js" }];
const originalSelfDescriptor = Object.getOwnPropertyDescriptor(globalThis, "self");

function navigationOptions(pathname: string): Parameters<NavigationRoute["match"]>[0] {
  return {
    event: {} as ExtendableEvent,
    request: { mode: "navigate" } as Request,
    sameOrigin: true,
    url: new URL(pathname, "https://runtime-dashboard.test"),
  };
}

describe("service worker", () => {
  afterEach(() => {
    if (originalSelfDescriptor) {
      Object.defineProperty(globalThis, "self", originalSelfDescriptor);
      return;
    }

    Reflect.deleteProperty(globalThis, "self");
  });

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();
    registeredWorkerEvents.clear();

    Object.defineProperty(globalThis, "self", {
      configurable: true,
      value: {
        __WB_MANIFEST: staticManifest,
        addEventListener: (type: string, listener: WorkerEventListener) => {
          registeredWorkerEvents.set(type, listener);
        },
        clients: { matchAll: clientMatchAll },
        skipWaiting: vi.fn(),
      },
      writable: true,
    });

    await import("./sw");
  });

  it("test_service_worker_has_no_authority_sync_or_authenticated_api_cache", async () => {
    const route = vi.mocked(registerRoute).mock.calls[0]?.[0];

    expect(vi.mocked(precacheAndRoute)).toHaveBeenCalledWith(staticManifest);
    expect(vi.mocked(registerRoute)).toHaveBeenCalledTimes(1);
    expect(route).toBeInstanceOf(NavigationRoute);
    expect(vi.mocked(createHandlerBoundToURL)).toHaveBeenCalledWith("/index.html");
    expect((route as NavigationRoute).handler.handle).toBe(navigationHandler);
    expect((route as NavigationRoute).match(navigationOptions("/workspace"))).toBe(true);
    expect((route as NavigationRoute).match(navigationOptions("/api/runs"))).toBe(false);
    expect((route as NavigationRoute).match(navigationOptions("/health"))).toBe(false);
    expect((route as NavigationRoute).match(navigationOptions("/ready"))).toBe(false);
    await expect(
      (route as NavigationRoute).handler.handle(navigationOptions("/workspace")),
    ).resolves.toBeInstanceOf(Response);
    expect(navigationHandler).toHaveBeenCalledTimes(1);
    expect(clientMatchAll).not.toHaveBeenCalled();
    expect(clientPostMessage).not.toHaveBeenCalled();
    expect(registeredWorkerEvents).toEqual(new Map());
  });
});
