import { useMemo } from "react";

import { useChatStore } from "../state/useChatStore";
import { useConversationContext } from "./useConversationContext";

/**
 * AI-generated follow-up suggestions based on current view and conversation state.
 */
export function useSuggestedQuestions(): string[] {
  const { messages } = useChatStore();
  const ctx = useConversationContext();

  return useMemo(() => {
    // If the latest system message has explicit suggestions, use those
    if (ctx.latestStructured?.suggestions && ctx.latestStructured.suggestions.length > 0) {
      return ctx.latestStructured.suggestions;
    }

    // Generate contextual suggestions
    return ctx.contextualSuggestions;
  }, [ctx.latestStructured?.suggestions, ctx.contextualSuggestions]);
}
