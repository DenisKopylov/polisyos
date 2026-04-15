import { beforeEach, describe, expect, it } from "vitest";

import type { ChatMessage, ConversationSession } from "./useChatStore";
import { useChatStore } from "./useChatStore";

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

describe("useChatStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useChatStore.setState({
      activeSessionId: null,
      currentRunId: null,
      isStreaming: false,
      messages: [],
      sessions: [],
    });
  });

  it("clears current conversation state when deleting the active session", () => {
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
