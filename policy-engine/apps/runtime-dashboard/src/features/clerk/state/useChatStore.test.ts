import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthorityLocalScope } from "@/app/offline/authorityLocalState";

import type {
  ChatMessage,
  ConversationSession,
  StructuredResponseData,
} from "./useChatStore";
import {
  hydrateChatStoreForIdentity,
  useChatStore,
} from "./useChatStore";

function createMessage(id: string, content: string): ChatMessage {
  return {
    content,
    id,
    role: "user",
    timestamp: Date.now(),
  };
}

function createSession(
  id: string,
  title: string,
  messages: ChatMessage[],
): ConversationSession {
  return {
    createdAt: Date.now(),
    id,
    messages,
    title,
    updatedAt: Date.now(),
  };
}

const identityA: AuthorityLocalScope = {
  tenantId: "tenant-a",
  userId: "user-a",
};

const identityB: AuthorityLocalScope = {
  tenantId: "tenant-b",
  userId: "user-b",
};

function storedEntries(): Array<[string, string]> {
  return Array.from({ length: localStorage.length }, (_, index) => {
    const key = localStorage.key(index);
    if (key === null) throw new Error("localStorage key disappeared");
    const value = localStorage.getItem(key);
    if (value === null) throw new Error("localStorage value disappeared");
    return [key, value];
  });
}

describe("useChatStore", () => {
  beforeEach(() => {
    hydrateChatStoreForIdentity(null);
    localStorage.clear();
    useChatStore.setState({
      activeSessionId: null,
      currentRunId: null,
      isStreaming: false,
      messages: [],
      sessions: [],
    });
  });

  it("clears before identity hydration and restores only that identity's sessions", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("A private message");
    const sessionA = useChatStore.getState().saveSession("A session");
    expect(sessionA).not.toBe("");

    useChatStore.setState({
      currentRunId: "run-a",
      isStreaming: true,
      messages: [createMessage("live-a", "must clear")],
    });
    hydrateChatStoreForIdentity(identityB);

    expect(useChatStore.getState()).toMatchObject({
      activeSessionId: null,
      currentRunId: null,
      isStreaming: false,
      messages: [],
      sessions: [],
    });

    useChatStore.getState().addUserMessage("B private message");
    const sessionB = useChatStore.getState().saveSession("B session");
    expect(sessionB).not.toBe("");

    hydrateChatStoreForIdentity(identityA);
    expect(useChatStore.getState()).toMatchObject({
      activeSessionId: null,
      currentRunId: null,
      isStreaming: false,
      messages: [],
    });
    expect(useChatStore.getState().sessions.map(({ id }) => id)).toEqual([
      sessionA,
    ]);
    expect(useChatStore.getState().sessions).not.toEqual(
      expect.arrayContaining([expect.objectContaining({ id: sessionB })]),
    );
  });

  it("persists a fixed-TTL envelope while excluding live and authority fields", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-16T12:00:00.000Z"));
    try {
      hydrateChatStoreForIdentity(identityA);
      useChatStore.getState().addSystemMessage({
        content: "Safe content",
        controlJobId: "control-1",
        error: "safe diagnostic",
        id: "message-rich",
        isProgressive: true,
        runFinishedAt: "2026-08-16T11:59:00Z",
        runId: "run-1",
        runStatus: "authority-must-not-persist",
        streamedTokens: "live tokens",
        structured: {
          confidence: 0.7,
          confidenceLevel: "medium",
          diff: [
            { after: "new", before: "old", sectionLabel: "Section" },
          ],
          keyFactors: [
            { direction: "positive", label: "Safe factor", magnitude: 0.8 },
          ],
          methodology: "Safe method",
          policyDomain: "Safe domain",
          sources: [
            {
              id: "source-1",
              label: "Safe source",
              type: "study",
              url: "https://example.test/source",
            },
          ],
          statusChips: ["authority-chip"],
          suggestions: ["safe follow-up"],
          verdict: "authority-verdict",
        },
        timestamp: Date.now(),
      });
      const sessionId = useChatStore.getState().saveSession("Safe session");
      expect(sessionId).not.toBe("");

      const entries = storedEntries();
      expect(entries).toHaveLength(1);
      const [physicalKey, raw] = entries[0];
      expect(physicalKey).not.toBe("polisyos-clerk-chat");
      expect(JSON.parse(raw)).toMatchObject({
        expiresAt: "2026-08-17T12:00:00.000Z",
        family: "clerk-chat-sessions",
        issuedAt: "2026-08-16T12:00:00.000Z",
        slot: "polisyos-clerk-chat",
        tenantId: "tenant-a",
        userId: "user-a",
        version: 1,
      });
      expect(raw).not.toContain("authority-must-not-persist");
      expect(raw).not.toContain("authority-verdict");
      expect(raw).not.toContain("authority-chip");
      expect(raw).not.toContain("live tokens");
      expect(raw).not.toContain("isProgressive");
      expect(raw).not.toContain("activeSessionId");
      expect(raw).not.toContain("currentRunId");
      expect(raw).not.toContain("isStreaming");

      hydrateChatStoreForIdentity(null);
      hydrateChatStoreForIdentity(identityA);
      const persistedMessage = useChatStore.getState().sessions[0]?.messages[0];
      expect(persistedMessage).toMatchObject({
        content: "Safe content",
        controlJobId: "control-1",
        error: "safe diagnostic",
        id: "message-rich",
        runFinishedAt: "2026-08-16T11:59:00Z",
        runId: "run-1",
        structured: {
          confidence: 0.7,
          confidenceLevel: "medium",
          diff: [
            { after: "new", before: "old", sectionLabel: "Section" },
          ],
          keyFactors: [
            { direction: "positive", label: "Safe factor", magnitude: 0.8 },
          ],
          methodology: "Safe method",
          policyDomain: "Safe domain",
          sources: [
            {
              id: "source-1",
              label: "Safe source",
              type: "study",
              url: "https://example.test/source",
            },
          ],
          suggestions: ["safe follow-up"],
        },
      });
      expect(persistedMessage).not.toHaveProperty("runStatus");
      expect(persistedMessage).not.toHaveProperty("streamedTokens");
      expect(persistedMessage).not.toHaveProperty("isProgressive");
      expect(persistedMessage?.structured).not.toHaveProperty("verdict");
      expect(persistedMessage?.structured).not.toHaveProperty("statusChips");
    } finally {
      vi.useRealTimers();
    }
  });

  it("rolls back a session save when the synchronous storage receipt fails", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("Original conversation");
    const originalSessionId = useChatStore
      .getState()
      .saveSession("Original session");
    expect(originalSessionId).not.toBe("");
    useChatStore.setState({
      messages: [createMessage("replacement", "Replacement conversation")],
    });

    const [physicalKey, originalRaw] = storedEntries()[0];
    const originalSessions = useChatStore.getState().sessions;
    const originalActiveSessionId = useChatStore.getState().activeSessionId;
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("quota unavailable");
      });
    try {
      expect(useChatStore.getState().saveSession("Must roll back")).toBe("");
      expect(useChatStore.getState().sessions).toEqual(originalSessions);
      expect(useChatStore.getState().activeSessionId).toBe(
        originalActiveSessionId,
      );
      expect(localStorage.getItem(physicalKey)).toBe(originalRaw);
      expect(setItem).toHaveBeenCalledTimes(1);
    } finally {
      setItem.mockRestore();
    }
  });

  it("rolls back an active-session delete when persistence fails", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("Session must survive");
    const sessionId = useChatStore.getState().saveSession("Surviving session");
    expect(sessionId).not.toBe("");
    useChatStore.setState({
      currentRunId: "run-delete",
      isStreaming: true,
      messages: [createMessage("message-delete", "Visible conversation")],
    });
    const [physicalKey, originalRaw] = storedEntries()[0];
    const originalState = {
      activeSessionId: useChatStore.getState().activeSessionId,
      currentRunId: useChatStore.getState().currentRunId,
      isStreaming: useChatStore.getState().isStreaming,
      messages: useChatStore.getState().messages,
      sessions: useChatStore.getState().sessions,
    };
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("delete persistence failed");
      });
    try {
      expect(() => useChatStore.getState().deleteSession(sessionId)).not.toThrow();
      expect(useChatStore.getState()).toMatchObject(originalState);
      expect(localStorage.getItem(physicalKey)).toBe(originalRaw);
      expect(setItem).toHaveBeenCalledTimes(1);
    } finally {
      setItem.mockRestore();
    }

    hydrateChatStoreForIdentity(null);
    hydrateChatStoreForIdentity(identityA);
    expect(useChatStore.getState().sessions.map(({ id }) => id)).toContain(
      sessionId,
    );
  });

  it("preserves the current conversation when new-session autosave fails", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("Do not discard me");
    const [physicalKey, originalRaw] = storedEntries()[0];
    const originalMessages = useChatStore.getState().messages;
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("storage write failed");
      });
    try {
      useChatStore.getState().newSession();
      expect(useChatStore.getState().messages).toEqual(originalMessages);
      expect(useChatStore.getState()).toMatchObject({
        activeSessionId: null,
        currentRunId: null,
        isStreaming: false,
        sessions: [],
      });
      expect(localStorage.getItem(physicalKey)).toBe(originalRaw);
      expect(setItem).toHaveBeenCalledTimes(1);
    } finally {
      setItem.mockRestore();
    }
  });

  it("rejects invalid, copied, expired, and forbidden stored bytes without rewriting", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-16T12:00:00.000Z"));
    try {
      hydrateChatStoreForIdentity(identityA);
      useChatStore.getState().addUserMessage("Persisted safely");
      expect(useChatStore.getState().saveSession("Valid seed")).not.toBe("");
      const [physicalKey, validRaw] = storedEntries()[0];

      const mutations: Array<
        readonly [string, (envelope: Record<string, unknown>) => void]
      > = [
        [
          "extended expiry",
          (envelope) => {
            envelope.expiresAt = "2026-08-17T13:00:00.000Z";
          },
        ],
        [
          "foreign family",
          (envelope) => {
            envelope.family = "foreign-family";
          },
        ],
        [
          "foreign version",
          (envelope) => {
            envelope.version = 2;
          },
        ],
        [
          "copied tenant",
          (envelope) => {
            envelope.tenantId = "tenant-b";
          },
        ],
        [
          "copied user",
          (envelope) => {
            envelope.userId = "user-b";
          },
        ],
        [
          "copied slot",
          (envelope) => {
            envelope.slot = "another-slot";
          },
        ],
        [
          "extra payload field",
          (envelope) => {
            const payload = envelope.encodedPayload as Record<string, unknown>;
            payload.extra = true;
          },
        ],
        [
          "forbidden stored message field",
          (envelope) => {
            const payload = envelope.encodedPayload as {
              sessions: Array<{ messages: Array<Record<string, unknown>> }>;
            };
            payload.sessions[0].messages[0].runStatus = "forged-authority";
          },
        ],
      ];

      for (const [label, mutate] of mutations) {
        vi.setSystemTime(new Date("2026-08-16T12:00:00.000Z"));
        hydrateChatStoreForIdentity(null);
        const envelope = JSON.parse(validRaw) as Record<string, unknown>;
        mutate(envelope);
        const mutatedRaw = JSON.stringify(envelope);
        localStorage.setItem(physicalKey, mutatedRaw);
        hydrateChatStoreForIdentity(identityA);
        expect({ label, sessions: useChatStore.getState().sessions }).toEqual({
          label,
          sessions: [],
        });
        expect({ label, raw: localStorage.getItem(physicalKey) }).toEqual({
          label,
          raw: mutatedRaw,
        });
      }

      hydrateChatStoreForIdentity(null);
      localStorage.setItem(physicalKey, validRaw);
      vi.setSystemTime(new Date("2026-08-17T12:00:00.000Z"));
      hydrateChatStoreForIdentity(identityA);
      expect(useChatStore.getState().sessions).toEqual([]);
      expect(localStorage.getItem(physicalKey)).toBe(validRaw);

      hydrateChatStoreForIdentity(null);
      localStorage.setItem(physicalKey, "{");
      vi.setSystemTime(new Date("2026-08-16T12:00:00.000Z"));
      hydrateChatStoreForIdentity(identityA);
      expect(useChatStore.getState().sessions).toEqual([]);
      expect(localStorage.getItem(physicalKey)).toBe("{");

      hydrateChatStoreForIdentity(null);
      localStorage.clear();
      localStorage.setItem("polisyos-clerk-chat", validRaw);
      vi.setSystemTime(new Date("2026-08-16T12:00:00.000Z"));
      hydrateChatStoreForIdentity(identityA);
      expect(useChatStore.getState().sessions).toEqual([]);
      expect(localStorage.getItem("polisyos-clerk-chat")).toBe(validRaw);
    } finally {
      vi.useRealTimers();
    }
  });

  it("performs no storage I/O when identity is missing or incomplete", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    try {
      hydrateChatStoreForIdentity(undefined);
      hydrateChatStoreForIdentity({ tenantId: "", userId: "user-a" });
      expect(useChatStore.getState()).toMatchObject({
        activeSessionId: null,
        currentRunId: null,
        isStreaming: false,
        messages: [],
        sessions: [],
      });
      expect(getItem).not.toHaveBeenCalled();
      expect(setItem).not.toHaveBeenCalled();
    } finally {
      getItem.mockRestore();
      setItem.mockRestore();
    }
  });

  it("contains a hostile codec value and preserves prior state and bytes", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("Original message");
    expect(useChatStore.getState().saveSession("Original session")).not.toBe("");

    const hostileMessage = {
      content: "Hostile message",
      id: "message-hostile",
      role: "system",
      get structured(): StructuredResponseData {
        throw new Error("codec getter escaped");
      },
      timestamp: Date.now(),
    } as ChatMessage;
    useChatStore.setState({ messages: [hostileMessage] });
    const [physicalKey, originalRaw] = storedEntries()[0];
    const originalSessions = useChatStore.getState().sessions;
    const originalActiveSessionId = useChatStore.getState().activeSessionId;

    let result: string | undefined;
    expect(() => {
      result = useChatStore.getState().saveSession("Hostile save");
    }).not.toThrow();
    expect(result).toBe("");
    expect(useChatStore.getState().sessions).toEqual(originalSessions);
    expect(useChatStore.getState().activeSessionId).toBe(originalActiveSessionId);
    expect(localStorage.getItem(physicalKey)).toBe(originalRaw);
  });

  it("contains hostile session-candidate getters before persistence", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("Original message");
    expect(useChatStore.getState().saveSession("Original session")).not.toBe("");

    const roleGetter = {
      content: "Hostile role",
      id: "message-role-getter",
      get role(): never {
        throw new Error("role getter escaped");
      },
      timestamp: Date.now(),
    } as unknown as ChatMessage;
    const contentProxy = new Proxy<ChatMessage>(
      {
        content: "Hostile content",
        id: "message-content-proxy",
        role: "user",
        timestamp: Date.now(),
      },
      {
        get(target, property, receiver) {
          if (property === "content") {
            throw new Error("content getter escaped");
          }
          return Reflect.get(target, property, receiver);
        },
      },
    );

    const messagesLengthProxy = new Proxy<ChatMessage[]>(
      [createMessage("message-length-proxy", "Hostile message array")],
      {
        get(target, property, receiver) {
          if (property === "length") {
            throw new Error("message-array length escaped");
          }
          return Reflect.get(target, property, receiver);
        },
      },
    );

    for (const [label, hostileMessages] of [
      ["role getter", [roleGetter]],
      ["content Proxy", [contentProxy]],
      ["message-array length Proxy", messagesLengthProxy],
    ] as const) {
      useChatStore.setState({ messages: hostileMessages as ChatMessage[] });
      const [physicalKey, originalRaw] = storedEntries()[0];
      const originalSessions = useChatStore.getState().sessions;
      const originalActiveSessionId = useChatStore.getState().activeSessionId;
      let result: string | undefined;
      expect(() => {
        result = useChatStore.getState().saveSession();
      }).not.toThrow();
      expect({ label, result }).toEqual({ label, result: "" });
      expect(useChatStore.getState().sessions).toEqual(originalSessions);
      expect(useChatStore.getState().activeSessionId).toBe(
        originalActiveSessionId,
      );
      expect(localStorage.getItem(physicalKey)).toBe(originalRaw);
    }
  });

  it("fails closed when storage reads throw", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("Stored message");
    expect(useChatStore.getState().saveSession("Stored session")).not.toBe("");
    const [physicalKey, originalRaw] = storedEntries()[0];
    hydrateChatStoreForIdentity(null);
    const getItem = vi
      .spyOn(Storage.prototype, "getItem")
      .mockImplementation(() => {
        throw new Error("storage unavailable");
      });
    try {
      expect(() => hydrateChatStoreForIdentity(identityA)).not.toThrow();
      expect(useChatStore.getState().sessions).toEqual([]);
    } finally {
      getItem.mockRestore();
    }
    expect(localStorage.getItem(physicalKey)).toBe(originalRaw);
  });

  it("fails closed when browser storage is absent", () => {
    const localStorageGetter = vi
      .spyOn(window, "localStorage", "get")
      .mockReturnValue(null as unknown as Storage);
    try {
      expect(() => hydrateChatStoreForIdentity(identityA)).not.toThrow();
      useChatStore.getState().addUserMessage("Cannot persist");
      expect(useChatStore.getState().saveSession("Cannot persist")).toBe("");
      expect(useChatStore.getState().sessions).toEqual([]);
    } finally {
      localStorageGetter.mockRestore();
    }
  });

  it("contains a throwing owner clock and preserves prior bytes", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("Original message");
    expect(useChatStore.getState().saveSession("Original session")).not.toBe("");
    useChatStore.setState({
      messages: [createMessage("message-clock", "Clock failure")],
    });
    const [physicalKey, originalRaw] = storedEntries()[0];
    const originalSessions = useChatStore.getState().sessions;
    const RealDate = Date;
    const ThrowingDate = function Date(): never {
      throw new Error("clock unavailable");
    } as unknown as DateConstructor;
    ThrowingDate.now = RealDate.now;
    ThrowingDate.parse = RealDate.parse;
    ThrowingDate.UTC = RealDate.UTC;
    vi.stubGlobal("Date", ThrowingDate);
    try {
      expect(useChatStore.getState().saveSession("Clock failure")).toBe("");
      expect(useChatStore.getState().sessions).toEqual(originalSessions);
    } finally {
      vi.unstubAllGlobals();
    }
    expect(localStorage.getItem(physicalKey)).toBe(originalRaw);
  });

  it("persists at most the newest fifty sessions", () => {
    hydrateChatStoreForIdentity(identityA);
    const sessions = Array.from({ length: 51 }, (_, index) =>
      createSession(
        `session-${index}`,
        `Session ${index}`,
        [createMessage(`message-${index}`, `Message ${index}`)],
      ),
    );
    useChatStore.setState({ sessions });
    hydrateChatStoreForIdentity(null);
    hydrateChatStoreForIdentity(identityA);
    expect(useChatStore.getState().sessions).toHaveLength(50);
    expect(useChatStore.getState().sessions.map(({ id }) => id)).toEqual(
      sessions.slice(0, 50).map(({ id }) => id),
    );
  });

  it("writes an owner-valid empty envelope when persistence is cleared", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().addUserMessage("Stored message");
    expect(useChatStore.getState().saveSession("Stored session")).not.toBe("");
    const [physicalKey] = storedEntries()[0];

    useChatStore.persist.clearStorage();
    const clearedRaw = localStorage.getItem(physicalKey);
    expect(clearedRaw).not.toBeNull();
    hydrateChatStoreForIdentity(null);
    hydrateChatStoreForIdentity(identityA);
    expect(useChatStore.getState().sessions).toEqual([]);
    expect(localStorage.getItem(physicalKey)).toBe(clearedRaw);
  });

  it("persists producer finished_at without persisting opaque runStatus", () => {
    hydrateChatStoreForIdentity(identityA);
    const producerMessage = {
      content: "Producer facts",
      id: "message-producer-facts",
      role: "system",
      runFinishedAt: "2026-03-10T10:05:00Z",
      runStatus: "awaiting_external_attestation",
      timestamp: Date.now(),
    } satisfies ChatMessage;

    useChatStore.getState().addSystemMessage(producerMessage);
    const sessionId = useChatStore.getState().saveSession("Producer facts");
    hydrateChatStoreForIdentity(null);
    hydrateChatStoreForIdentity(identityA);
    useChatStore.getState().loadSession(sessionId);

    expect(useChatStore.getState().messages[0]).toMatchObject({
      runFinishedAt: "2026-03-10T10:05:00Z",
    });
    expect(useChatStore.getState().messages[0]).not.toHaveProperty("runStatus");
  });

  it("clears current conversation state when deleting the active session", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.setState({
      activeSessionId: "session-active",
      currentRunId: "run-1",
      isStreaming: true,
      messages: [createMessage("message-1", "hello")],
      sessions: [
        createSession("session-active", "Current", [
          createMessage("message-1", "hello"),
        ]),
        createSession("session-other", "Other", [
          createMessage("message-2", "world"),
        ]),
      ],
    });

    useChatStore.getState().deleteSession("session-active");

    expect(useChatStore.getState()).toMatchObject({
      activeSessionId: null,
      currentRunId: null,
      isStreaming: false,
      messages: [],
    });
    expect(useChatStore.getState().sessions).toEqual([
      expect.objectContaining({ id: "session-other" }),
    ]);
  });

  it("preserves the current conversation when deleting an inactive session", () => {
    hydrateChatStoreForIdentity(identityA);
    useChatStore.setState({
      activeSessionId: "session-active",
      currentRunId: "run-2",
      isStreaming: false,
      messages: [createMessage("message-active", "stay visible")],
      sessions: [
        createSession("session-active", "Current", [
          createMessage("message-active", "stay visible"),
        ]),
        createSession("session-inactive", "Old", [
          createMessage("message-old", "remove me"),
        ]),
      ],
    });

    useChatStore.getState().deleteSession("session-inactive");

    expect(useChatStore.getState()).toMatchObject({
      activeSessionId: "session-active",
      currentRunId: "run-2",
      isStreaming: false,
      messages: [expect.objectContaining({ id: "message-active" })],
    });
    expect(useChatStore.getState().sessions).toEqual([
      expect.objectContaining({ id: "session-active" }),
    ]);
  });
});
