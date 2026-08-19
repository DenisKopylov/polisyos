import { StrictMode } from "react";
import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthorityLocalScope } from "@/app/offline/authorityLocalState";

const { bridgeCallMock, chatRenderMock, useAuthzMock } = vi.hoisted(() => ({
  bridgeCallMock: vi.fn(),
  chatRenderMock: vi.fn(),
  useAuthzMock: vi.fn(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthz: () => useAuthzMock(),
}));

vi.mock("../state/useChatStore", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../state/useChatStore")>();
  return {
    ...actual,
    hydrateChatStoreForIdentity: (
      scope: AuthorityLocalScope | null | undefined,
    ) => {
      bridgeCallMock(scope);
      actual.hydrateChatStoreForIdentity(scope);
    },
  };
});

vi.mock("../components/ChatContainer", () => ({
  ChatContainer: () => {
    chatRenderMock();
    return <div data-testid="clerk-chat-container" />;
  },
}));

import ClerkChatPage from "./ClerkChatPage";
import {
  hydrateChatStoreForIdentity,
  type ConversationSession,
  useChatStore,
} from "../state/useChatStore";

const identityA: AuthorityLocalScope = {
  tenantId: "tenant-a",
  userId: "user-a",
};

type BoundaryEvent =
  | {
      kind: "bridge";
      scope: readonly [tenantId: string, userId: string] | null;
    }
  | {
      activeSessionId: string | null;
      currentRunId: string | null;
      isStreaming: boolean;
      kind: "render";
      messageIds: string[];
      phase: string;
      sessionIds: string[];
    };

let events: BoundaryEvent[] = [];
let phase = "setup";

function session(id: string): ConversationSession {
  return {
    createdAt: Date.now(),
    id,
    messages: [
      {
        content: `${id} private content`,
        id: `${id}-message`,
        role: "user",
        timestamp: Date.now(),
      },
    ],
    title: id,
    updatedAt: Date.now(),
  };
}

function putStaleSession(id: string): void {
  useChatStore.setState({
    activeSessionId: id,
    currentRunId: `${id}-run`,
    isStreaming: true,
    messages: session(id).messages,
    sessions: [session(id)],
  });
}

function readyAuthz(scope: AuthorityLocalScope) {
  return {
    status: "ready",
    user: { tenant_id: scope.tenantId, user_id: scope.userId },
  };
}

function expectCurrentPhaseBoundEmpty(
  expectedScope: AuthorityLocalScope,
): void {
  const firstBridge = events.findIndex(
    (event) =>
      event.kind === "bridge" &&
      event.scope?.[0] === expectedScope.tenantId &&
      event.scope[1] === expectedScope.userId,
  );
  const renders = events.filter(
    (event): event is Extract<BoundaryEvent, { kind: "render" }> =>
      event.kind === "render" && event.phase === phase,
  );
  const firstRender = events.findIndex(
    (event) => event.kind === "render" && event.phase === phase,
  );

  expect(firstBridge).toBeGreaterThanOrEqual(0);
  expect(firstRender).toBeGreaterThan(firstBridge);
  expect(renders.length).toBeGreaterThan(0);
  expect(
    renders.every(
      (event) =>
        event.activeSessionId === null &&
        event.currentRunId === null &&
        !event.isStreaming &&
        event.messageIds.length === 0 &&
        event.sessionIds.length === 0,
    ),
  ).toBe(true);
}

function expectCurrentPhaseHydrated(
  expectedScope: AuthorityLocalScope,
  expectedSessionId: string,
): void {
  const firstBridge = events.findIndex(
    (event) =>
      event.kind === "bridge" &&
      event.scope?.[0] === expectedScope.tenantId &&
      event.scope[1] === expectedScope.userId,
  );
  const renders = events.filter(
    (event): event is Extract<BoundaryEvent, { kind: "render" }> =>
      event.kind === "render" && event.phase === phase,
  );
  const firstRender = events.findIndex(
    (event) => event.kind === "render" && event.phase === phase,
  );

  expect(firstBridge).toBeGreaterThanOrEqual(0);
  expect(firstRender).toBeGreaterThan(firstBridge);
  expect(renders.length).toBeGreaterThan(0);
  expect(renders.every((event) => !event.isStreaming)).toBe(true);
  expect(renders.at(-1)?.sessionIds).toEqual([expectedSessionId]);
}

describe("ClerkChatPage identity bridge", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-16T12:00:00.000Z"));
    events = [];
    phase = "setup";
    bridgeCallMock.mockReset();
    chatRenderMock.mockReset();
    useAuthzMock.mockReset();
    bridgeCallMock.mockImplementation(
      (scope: AuthorityLocalScope | null | undefined) => {
        events.push({
          kind: "bridge",
          scope: scope ? [scope.tenantId, scope.userId] : null,
        });
      },
    );
    chatRenderMock.mockImplementation(() => {
      const state = useChatStore.getState();
      events.push({
        activeSessionId: state.activeSessionId,
        currentRunId: state.currentRunId,
        isStreaming: state.isStreaming,
        kind: "render",
        messageIds: state.messages.map(({ id }) => id),
        phase,
        sessionIds: state.sessions.map(({ id }) => id),
      });
    });
    hydrateChatStoreForIdentity(null);
    localStorage.clear();
    useChatStore.setState({
      activeSessionId: null,
      currentRunId: null,
      isStreaming: false,
      messages: [],
      sessions: [],
    });
    events = [];
  });

  afterEach(() => {
    hydrateChatStoreForIdentity(null);
    localStorage.clear();
    vi.useRealTimers();
  });

  it("test_clerk_page_binds_current_identity_before_hydration", async () => {
    putStaleSession("prior-absent");
    useAuthzMock.mockReturnValue({
      status: "loading",
      user: { tenant_id: identityA.tenantId, user_id: identityA.userId },
    });
    phase = "absent";
    const view = render(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );

    expect(events.some((event) => event.kind === "render")).toBe(false);
    expect(events).toContainEqual({ kind: "bridge", scope: null });
    expect(useChatStore.getState().sessions).toEqual([]);

    vi.setSystemTime(new Date("2026-08-16T12:00:00.000Z"));
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("Expired private content");
    const persistedSessionId = useChatStore
      .getState()
      .saveSession("Expiry boundary session");
    expect(persistedSessionId).not.toBe("");
    expect(localStorage).toHaveLength(1);
    hydrateChatStoreForIdentity(null);

    events = [];
    phase = "valid-hydration";
    useAuthzMock.mockReturnValue(readyAuthz(identityA));
    view.rerender(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );
    await act(async () => {
      await Promise.resolve();
    });
    expectCurrentPhaseHydrated(identityA, persistedSessionId);

    events = [];
    phase = "between-hydrations";
    useAuthzMock.mockReturnValue({ status: "loading", user: undefined });
    view.rerender(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );
    expect(events.some((event) => event.kind === "render")).toBe(false);
    expect(events).toContainEqual({ kind: "bridge", scope: null });

    putStaleSession("prior-expired");
    events = [];
    phase = "expired";
    vi.setSystemTime(new Date("2026-08-17T12:00:00.000Z"));
    useAuthzMock.mockReturnValue(readyAuthz(identityA));
    view.rerender(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );
    await act(async () => {
      await Promise.resolve();
    });
    expectCurrentPhaseBoundEmpty(identityA);

    const tenantB = { tenantId: "tenant-b", userId: identityA.userId };
    putStaleSession("prior-tenant");
    events = [];
    phase = "changed-tenant";
    useAuthzMock.mockReturnValue(readyAuthz(tenantB));
    view.rerender(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );
    expectCurrentPhaseBoundEmpty(tenantB);

    const userB = { tenantId: tenantB.tenantId, userId: "user-b" };
    putStaleSession("prior-user");
    events = [];
    phase = "changed-user";
    useAuthzMock.mockReturnValue(readyAuthz(userB));
    view.rerender(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );
    expectCurrentPhaseBoundEmpty(userB);

    const collisionA = { tenantId: "a\u0000b", userId: "c" };
    events = [];
    phase = "collision-a";
    useAuthzMock.mockReturnValue(readyAuthz(collisionA));
    view.rerender(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );
    expectCurrentPhaseBoundEmpty(collisionA);

    putStaleSession("prior-delimiter-collision");
    const collisionB = { tenantId: "a", userId: "b\u0000c" };
    events = [];
    phase = "collision-b";
    useAuthzMock.mockReturnValue(readyAuthz(collisionB));
    view.rerender(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );
    expectCurrentPhaseBoundEmpty(collisionB);

    putStaleSession("prior-error");
    events = [];
    phase = "error";
    useAuthzMock.mockReturnValue({
      status: "error",
      user: { tenant_id: collisionB.tenantId, user_id: collisionB.userId },
    });
    view.rerender(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );
    expect(events.some((event) => event.kind === "render")).toBe(false);
    expect(events).toContainEqual({ kind: "bridge", scope: null });
    expect(useChatStore.getState().sessions).toEqual([]);
  });

  it.each(["tenant_id", "user_id"] as const)(
    "contains a throwing %s getter at the page boundary",
    (hostileField) => {
      putStaleSession(`prior-hostile-${hostileField}`);
      useAuthzMock.mockReturnValue({
        status: "ready",
        user: {
          get tenant_id(): string {
            if (hostileField === "tenant_id") {
              throw new Error("tenant getter escaped");
            }
            return "tenant-hostile";
          },
          get user_id(): string {
            if (hostileField === "user_id") {
              throw new Error("user getter escaped");
            }
            return "user-hostile";
          },
        },
      });

      expect(() =>
        render(
          <StrictMode>
            <ClerkChatPage />
          </StrictMode>,
        ),
      ).not.toThrow();
      expect(chatRenderMock).not.toHaveBeenCalled();
      expect(events).toContainEqual({ kind: "bridge", scope: null });
      expect(useChatStore.getState()).toMatchObject({
        activeSessionId: null,
        currentRunId: null,
        isStreaming: false,
        messages: [],
        sessions: [],
      });
    },
  );

  it("snapshots changing identity getters once per render", () => {
    let tenantReads = 0;
    let userReads = 0;
    useAuthzMock.mockReturnValue({
      status: "ready",
      user: {
        get tenant_id(): string {
          tenantReads += 1;
          return `tenant-${tenantReads}`;
        },
        get user_id(): string {
          userReads += 1;
          return `user-${userReads}`;
        },
      },
    });

    render(
      <StrictMode>
        <ClerkChatPage />
      </StrictMode>,
    );

    expect({ tenantReads, userReads }).toEqual({
      tenantReads: 2,
      userReads: 2,
    });
    expect(
      events
        .filter((event) => event.kind === "bridge")
        .map((event) => event.scope),
    ).toEqual([
      ["tenant-2", "user-2"],
      ["tenant-2", "user-2"],
    ]);
    expect(
      events
        .filter(
          (event): event is Extract<BoundaryEvent, { kind: "render" }> =>
            event.kind === "render",
        )
        .every(
          (event) =>
            event.messageIds.length === 0 &&
            !event.isStreaming &&
            event.sessionIds.length === 0,
        ),
    ).toBe(true);
  });
});
