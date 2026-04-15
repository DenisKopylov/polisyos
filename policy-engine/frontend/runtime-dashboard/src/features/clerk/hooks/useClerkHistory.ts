import { useMemo, useState } from "react";

import {
  useChatStore,
  type ConversationSession,
} from "../state/useChatStore";

export type HistorySearchResult = {
  session: ConversationSession;
  /** Matching message snippets with context. */
  matches: {
    messageId: string;
    snippet: string;
    role: "user" | "system";
  }[];
};

function searchSessions(
  sessions: ConversationSession[],
  query: string,
): HistorySearchResult[] {
  if (!query.trim()) {
    return sessions.map((session) => ({ session, matches: [] }));
  }

  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  const results: HistorySearchResult[] = [];

  for (const session of sessions) {
    const matches: HistorySearchResult["matches"] = [];

    for (const msg of session.messages) {
      const text = msg.content.toLowerCase();
      if (terms.every((term) => text.includes(term))) {
        // Build snippet around first match
        const firstTermIdx = text.indexOf(terms[0]);
        const start = Math.max(0, firstTermIdx - 30);
        const end = Math.min(msg.content.length, firstTermIdx + terms[0].length + 60);
        const snippet =
          (start > 0 ? "..." : "") +
          msg.content.slice(start, end) +
          (end < msg.content.length ? "..." : "");

        matches.push({
          messageId: msg.id,
          snippet,
          role: msg.role,
        });
      }
    }

    // Also check title
    const titleMatch = terms.every((term) =>
      session.title.toLowerCase().includes(term),
    );

    if (matches.length > 0 || titleMatch) {
      results.push({ session, matches });
    }
  }

  return results;
}

/**
 * Conversation history with search.
 * Provides search over persisted sessions and session management.
 */
export function useClerkHistory() {
  const { sessions, loadSession, deleteSession, newSession, saveSession } =
    useChatStore();
  const [searchQuery, setSearchQuery] = useState("");

  const searchResults = useMemo(
    () => searchSessions(sessions, searchQuery),
    [sessions, searchQuery],
  );

  return {
    sessions,
    searchQuery,
    setSearchQuery,
    searchResults,
    loadSession,
    deleteSession,
    newSession,
    saveSession,
    totalSessions: sessions.length,
  };
}
