import { create } from "zustand";
import { persist, type PersistStorage } from "zustand/middleware";
import { z } from "zod";

import {
  createAuthorityLocalStateEnvelopeFamily,
  type AuthorityLocalScope,
} from "@/app/offline/authorityLocalState";

export type ChatRole = "user" | "system";

export type SourceCitation = {
  id: string;
  label: string;
  url?: string;
  type: "dataset" | "legislation" | "study" | "model" | "governance";
};

export type KeyFactor = {
  label: string;
  direction: "positive" | "negative" | "neutral";
  magnitude: number; // 0..1
};

export type StructuredResponseData = {
  verdict?: string;
  confidence?: number;
  confidenceLevel?: string;
  keyFactors?: KeyFactor[];
  sources?: SourceCitation[];
  methodology?: string;
  policyDomain?: string;
  /** Suggested follow-up questions based on this response. */
  suggestions?: string[];
  /** Inline status chips shown during progressive build. */
  statusChips?: string[];
  /** If the response contains a diff/draft proposal. */
  diff?: { before: string; after: string; sectionLabel?: string }[];
};

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: number;
  runId?: string;
  controlJobId?: string;
  runStatus?: string;
  runFinishedAt?: string;
  error?: string;
  /** Structured data for rich response rendering. */
  structured?: StructuredResponseData;
  /** Tokens streamed so far (for progressive rendering). */
  streamedTokens?: string;
  /** Whether this message is still being progressively built. */
  isProgressive?: boolean;
};

export function hasProducerFinishedAt(
  value: string | null | undefined,
): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export type ConversationSession = {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
};

const CHAT_STORAGE_FAMILY = "clerk-chat-sessions";
const CHAT_STORAGE_SLOT = "polisyos-clerk-chat";
const CHAT_STORAGE_TTL_MS = 24 * 60 * 60 * 1_000;
const CHAT_STORAGE_VERSION = 1;

let currentChatScope: AuthorityLocalScope | null = null;
let persistenceSuppressed = false;
let persistenceWriteAttempts = 0;
let lastPersistenceReceipt = false;

const keyFactorPersistenceSchema = z
  .object({
    direction: z.enum(["negative", "neutral", "positive"]),
    label: z.string(),
    magnitude: z.number(),
  })
  .strict();
const sourceCitationPersistenceSchema = z
  .object({
    id: z.string(),
    label: z.string(),
    type: z.enum(["dataset", "governance", "legislation", "model", "study"]),
    url: z.string().optional(),
  })
  .strict();
const diffPersistenceSchema = z
  .object({
    after: z.string(),
    before: z.string(),
    sectionLabel: z.string().optional(),
  })
  .strict();
const structuredResponsePersistenceSchema = z
  .object({
    confidence: z.number().optional(),
    confidenceLevel: z.string().optional(),
    diff: z.array(diffPersistenceSchema).optional(),
    keyFactors: z.array(keyFactorPersistenceSchema).optional(),
    methodology: z.string().optional(),
    policyDomain: z.string().optional(),
    sources: z.array(sourceCitationPersistenceSchema).optional(),
    suggestions: z.array(z.string()).optional(),
  })
  .strict();
const chatMessagePersistenceSchema = z
  .object({
    content: z.string(),
    controlJobId: z.string().optional(),
    error: z.string().optional(),
    id: z.string(),
    role: z.enum(["system", "user"]),
    runFinishedAt: z.string().optional(),
    runId: z.string().optional(),
    structured: structuredResponsePersistenceSchema.optional(),
    timestamp: z.number(),
  })
  .strict();
const conversationSessionPersistenceSchema = z
  .object({
    createdAt: z.number(),
    id: z.string(),
    messages: z.array(chatMessagePersistenceSchema),
    title: z.string(),
    updatedAt: z.number(),
  })
  .strict();
const persistedChatStateSchema = z
  .object({ sessions: z.array(conversationSessionPersistenceSchema).max(50) })
  .strict();

type PersistedChatState = z.infer<typeof persistedChatStateSchema>;

function decodePersistedChatState(encoded: unknown): PersistedChatState | null {
  const decoded = persistedChatStateSchema.safeParse(encoded);
  return decoded.success ? decoded.data : null;
}

function encodeStructured(
  structured: StructuredResponseData,
): StructuredResponseData {
  return {
    ...(structured.confidence === undefined
      ? {}
      : { confidence: structured.confidence }),
    ...(structured.confidenceLevel === undefined
      ? {}
      : { confidenceLevel: structured.confidenceLevel }),
    ...(structured.keyFactors === undefined
      ? {}
      : { keyFactors: structured.keyFactors }),
    ...(structured.sources === undefined ? {} : { sources: structured.sources }),
    ...(structured.methodology === undefined
      ? {}
      : { methodology: structured.methodology }),
    ...(structured.policyDomain === undefined
      ? {}
      : { policyDomain: structured.policyDomain }),
    ...(structured.suggestions === undefined
      ? {}
      : { suggestions: structured.suggestions }),
    ...(structured.diff === undefined ? {} : { diff: structured.diff }),
  };
}

function encodeMessage(message: ChatMessage): ChatMessage {
  return {
    content: message.content,
    id: message.id,
    role: message.role,
    timestamp: message.timestamp,
    ...(message.runId === undefined ? {} : { runId: message.runId }),
    ...(message.controlJobId === undefined
      ? {}
      : { controlJobId: message.controlJobId }),
    ...(message.runFinishedAt === undefined
      ? {}
      : { runFinishedAt: message.runFinishedAt }),
    ...(message.error === undefined ? {} : { error: message.error }),
    ...(message.structured === undefined
      ? {}
      : { structured: encodeStructured(message.structured) }),
  };
}

function encodePersistedChatState(value: PersistedChatState): PersistedChatState {
  const encoded = {
    sessions: value.sessions.map((session) => ({
      createdAt: session.createdAt,
      id: session.id,
      messages: session.messages.map(encodeMessage),
      title: session.title,
      updatedAt: session.updatedAt,
    })),
  };
  const validated = decodePersistedChatState(encoded);
  if (!validated) throw new Error("Clerk chat persistence payload is invalid.");
  return validated;
}

const chatEnvelopeOwner = createAuthorityLocalStateEnvelopeFamily({
  clock: () => new Date(),
  codec: {
    decode: decodePersistedChatState,
    encode: encodePersistedChatState,
  },
  family: CHAT_STORAGE_FAMILY,
  ttlMs: CHAT_STORAGE_TTL_MS,
  version: CHAT_STORAGE_VERSION,
});

function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

const chatPersistStorage: PersistStorage<PersistedChatState, boolean> = {
  getItem(name) {
    const physicalKey = chatEnvelopeOwner.key({
      scope: currentChatScope,
      slot: name,
    });
    if (!physicalKey) return null;
    try {
      const raw = browserStorage()?.getItem(physicalKey);
      if (!raw) return null;
      const state = chatEnvelopeOwner.decode({
        envelope: JSON.parse(raw) as unknown,
        fallback: null,
        scope: currentChatScope,
        slot: name,
      });
      return state === null
        ? null
        : { state, version: CHAT_STORAGE_VERSION };
    } catch {
      return null;
    }
  },
  removeItem(name) {
    return chatPersistStorage.setItem(name, {
      state: { sessions: [] },
      version: CHAT_STORAGE_VERSION,
    });
  },
  setItem(name, value) {
    if (persistenceSuppressed) return true;
    persistenceWriteAttempts += 1;
    lastPersistenceReceipt = false;
    const issued = chatEnvelopeOwner.encode({
      scope: currentChatScope,
      slot: name,
      value: value.state,
    });
    if (!issued) return false;
    try {
      const storage = browserStorage();
      if (!storage) return false;
      storage.setItem(issued.key, JSON.stringify(issued.envelope));
      lastPersistenceReceipt = true;
      return true;
    } catch {
      return false;
    }
  },
};

type ChatState = {
  messages: ChatMessage[];
  isStreaming: boolean;
  currentRunId: string | null;
  /** Persisted conversation sessions. */
  sessions: ConversationSession[];
  /** Active session ID. */
  activeSessionId: string | null;
  addUserMessage: (content: string) => string;
  addSystemMessage: (message: Omit<ChatMessage, "role">) => void;
  updateSystemMessage: (id: string, update: Partial<ChatMessage>) => void;
  appendStreamedTokens: (id: string, tokens: string) => void;
  setStreaming: (streaming: boolean) => void;
  setCurrentRunId: (runId: string | null) => void;
  clearHistory: () => void;
  /** Save current conversation as a session. */
  saveSession: (title?: string) => string;
  /** Load a saved session. */
  loadSession: (sessionId: string) => void;
  /** Delete a saved session. */
  deleteSession: (sessionId: string) => void;
  /** Start a fresh conversation. */
  newSession: () => void;
};

let messageCounter = 0;
function nextMessageId(): string {
  return `msg_${Date.now()}_${++messageCounter}`;
}

function nextSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      isStreaming: false,
      currentRunId: null,
      sessions: [],
      activeSessionId: null,

      addUserMessage: (content) => {
        const id = nextMessageId();
        set((state) => ({
          messages: [
            ...state.messages,
            { id, role: "user", content, timestamp: Date.now() },
          ],
        }));
        return id;
      },

      addSystemMessage: (message) => {
        set((state) => ({
          messages: [...state.messages, { ...message, role: "system" }],
        }));
      },

      updateSystemMessage: (id, update) => {
        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.id === id ? { ...msg, ...update } : msg,
          ),
        }));
      },

      appendStreamedTokens: (id, tokens) => {
        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.id === id
              ? { ...msg, streamedTokens: (msg.streamedTokens ?? "") + tokens }
              : msg,
          ),
        }));
      },

      setStreaming: (streaming) => set({ isStreaming: streaming }),
      setCurrentRunId: (runId) => set({ currentRunId: runId }),

      clearHistory: () =>
        set({
          messages: [],
          isStreaming: false,
          currentRunId: null,
          activeSessionId: null,
        }),

      saveSession: (title) => {
        let previousSessions: ConversationSession[] = [];
        let previousActiveSessionId: string | null = null;
        let snapshotCaptured = false;
        const rollbackSessionSlice = () => {
          if (!snapshotCaptured) return;
          persistenceSuppressed = true;
          try {
            set({
              activeSessionId: previousActiveSessionId,
              sessions: previousSessions,
            });
          } catch {
            // Zustand applies state before notifying listeners; containment
            // must still prevent a hostile listener from escaping this API.
          } finally {
            persistenceSuppressed = false;
          }
        };
        try {
          const state = get();
          if (state.messages.length === 0) return "";
          previousSessions = state.sessions;
          previousActiveSessionId = state.activeSessionId;
          snapshotCaptured = true;
          const sessionId = state.activeSessionId ?? nextSessionId();
          const firstUserMsg = state.messages.find((m) => m.role === "user");
          const sessionTitle =
            title ||
            firstUserMsg?.content.slice(0, 60) ||
            "Untitled conversation";

          const attemptsBeforeSave = persistenceWriteAttempts;
          set((prev) => {
            const existing = prev.sessions.find((s) => s.id === sessionId);
            const session: ConversationSession = {
              id: sessionId,
              title: sessionTitle,
              messages: prev.messages,
              createdAt: existing?.createdAt ?? Date.now(),
              updatedAt: Date.now(),
            };
            return {
              activeSessionId: sessionId,
              sessions: existing
                ? prev.sessions.map((s) => (s.id === sessionId ? session : s))
                : [session, ...prev.sessions],
            };
          });
          if (
            persistenceWriteAttempts === attemptsBeforeSave + 1 &&
            lastPersistenceReceipt
          ) {
            return sessionId;
          }
          rollbackSessionSlice();
          return "";
        } catch {
          rollbackSessionSlice();
          return "";
        }
      },

      loadSession: (sessionId) => {
        const session = get().sessions.find((s) => s.id === sessionId);
        if (!session) return;
        set({
          messages: session.messages,
          activeSessionId: sessionId,
          isStreaming: false,
          currentRunId: null,
        });
      },

      deleteSession: (sessionId) => {
        const state = get();
        const snapshot = {
          activeSessionId: state.activeSessionId,
          currentRunId: state.currentRunId,
          isStreaming: state.isStreaming,
          messages: state.messages,
          sessions: state.sessions,
        };
        const rollbackDeletion = () => {
          persistenceSuppressed = true;
          try {
            set(snapshot);
          } catch {
            // The state assignment precedes Zustand listener notification.
          } finally {
            persistenceSuppressed = false;
          }
        };
        const attemptsBeforeDelete = persistenceWriteAttempts;
        try {
          set((current) => ({
            sessions: current.sessions.filter((s) => s.id !== sessionId),
            messages:
              current.activeSessionId === sessionId ? [] : current.messages,
            isStreaming:
              current.activeSessionId === sessionId
                ? false
                : current.isStreaming,
            currentRunId:
              current.activeSessionId === sessionId
                ? null
                : current.currentRunId,
            activeSessionId:
              current.activeSessionId === sessionId
                ? null
                : current.activeSessionId,
          }));
          if (
            persistenceWriteAttempts === attemptsBeforeDelete + 1 &&
            lastPersistenceReceipt
          ) {
            return;
          }
        } catch {
          rollbackDeletion();
          return;
        }
        rollbackDeletion();
      },

      newSession: () => {
        const state = get();
        // Auto-save current if non-empty
        if (state.messages.length > 0 && !state.saveSession()) return;
        set({
          messages: [],
          isStreaming: false,
          currentRunId: null,
          activeSessionId: null,
        });
      },
    }),
    {
      name: CHAT_STORAGE_SLOT,
      partialize: (state) => ({
        sessions: state.sessions.slice(0, 50), // Keep last 50 sessions
      }),
      skipHydration: true,
      storage: chatPersistStorage,
      version: CHAT_STORAGE_VERSION,
    },
  ),
);

/** Clears live chat state, then hydrates sessions for one verified identity. */
export function hydrateChatStoreForIdentity(
  scope: AuthorityLocalScope | null | undefined,
): void {
  currentChatScope = null;
  persistenceSuppressed = true;
  try {
    useChatStore.setState({
      activeSessionId: null,
      currentRunId: null,
      isStreaming: false,
      messages: [],
      sessions: [],
    });
  } finally {
    persistenceSuppressed = false;
  }
  if (!chatEnvelopeOwner.key({ scope, slot: CHAT_STORAGE_SLOT })) return;
  currentChatScope = Object.freeze({
    tenantId: scope!.tenantId,
    userId: scope!.userId,
  });
  void useChatStore.persist.rehydrate();
}
