import { act, renderHook } from "@testing-library/react";

import { useChatStore } from "../state/useChatStore";
import { useConversationContext } from "./useConversationContext";

const COMPLETION_SUGGESTION =
  "What are the key uncertainties in this analysis?";

describe("useConversationContext", () => {
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

  it("does not generate completed-run suggestions from status text without finished_at", () => {
    useChatStore.getState().addUserMessage("Assess the intervention");
    useChatStore.getState().addSystemMessage({
      content: "Producer status remains opaque",
      id: "system-opaque",
      runStatus: "completed",
      timestamp: Date.now(),
    });
    useChatStore.getState().addUserMessage("Continue");

    const { result } = renderHook(() => useConversationContext());

    expect(result.current.contextualSuggestions).not.toContain(
      COMPLETION_SUGGESTION,
    );

    act(() => {
      useChatStore.getState().updateSystemMessage("system-opaque", {
        runFinishedAt: "2026-03-10T10:05:00Z",
      });
    });

    expect(result.current.contextualSuggestions).toContain(
      COMPLETION_SUGGESTION,
    );
  });

  it("does not generate completed-run suggestions from whitespace-only finished_at", () => {
    useChatStore.getState().addUserMessage("Assess the intervention");
    useChatStore.getState().addSystemMessage({
      content: "Producer completion is absent",
      id: "system-whitespace",
      runFinishedAt: "   ",
      timestamp: Date.now(),
    });
    useChatStore.getState().addUserMessage("Continue");

    const { result } = renderHook(() => useConversationContext());

    expect(result.current.contextualSuggestions).not.toContain(
      COMPLETION_SUGGESTION,
    );
  });
});
