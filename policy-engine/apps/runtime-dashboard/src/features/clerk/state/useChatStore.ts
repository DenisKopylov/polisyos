import { create } from "zustand";
import { persist } from "zustand/middleware";

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
        const state = get();
        if (state.messages.length === 0) return "";
        const sessionId = state.activeSessionId ?? nextSessionId();
        const firstUserMsg = state.messages.find((m) => m.role === "user");
        const sessionTitle =
          title ||
          firstUserMsg?.content.slice(0, 60) ||
          "Untitled conversation";

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
        return sessionId;
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
        set((state) => ({
          sessions: state.sessions.filter((s) => s.id !== sessionId),
          messages: state.activeSessionId === sessionId ? [] : state.messages,
          isStreaming:
            state.activeSessionId === sessionId ? false : state.isStreaming,
          currentRunId:
            state.activeSessionId === sessionId ? null : state.currentRunId,
          activeSessionId:
            state.activeSessionId === sessionId ? null : state.activeSessionId,
        }));
      },

      newSession: () => {
        const state = get();
        // Auto-save current if non-empty
        if (state.messages.length > 0) {
          state.saveSession();
        }
        set({
          messages: [],
          isStreaming: false,
          currentRunId: null,
          activeSessionId: null,
        });
      },
    }),
    {
      name: "polisyos-clerk-chat",
      partialize: (state) => ({
        sessions: state.sessions.slice(0, 50), // Keep last 50 sessions
      }),
    },
  ),
);
