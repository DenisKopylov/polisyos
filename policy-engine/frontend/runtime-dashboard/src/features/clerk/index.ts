export { clerkChatRoute } from "./route";

// Components
export { ChatContainer } from "./components/ChatContainer";
export { ChatMessage } from "./components/ChatMessage";
export { ChatInput } from "./components/ChatInput";
export { ChatStreamIndicator } from "./components/ChatStreamIndicator";
export { ClerkHistoryList } from "./components/ClerkHistoryList";
export { ClerkStructuredResponse } from "./components/ClerkStructuredResponse";
export { ClerkSuggestionChips } from "./components/ClerkSuggestionChips";
export { ClerkFollowUpBar } from "./components/ClerkFollowUpBar";
export { ClerkProgressiveStream } from "./components/ClerkProgressiveStream";
export { AIDiffView } from "./components/AIDiffView";
export { ConversationHistorySearch } from "./components/ConversationHistorySearch";
export { ExportConversation } from "./components/ExportConversation";

// Hooks
export { useClerkNlRun } from "./hooks/useClerkNlRun";
export { useConversationContext } from "./hooks/useConversationContext";
export { useClerkHistory } from "./hooks/useClerkHistory";
export { useSuggestedQuestions } from "./hooks/useSuggestedQuestions";

// State
export { useChatStore } from "./state/useChatStore";
export type {
  ChatMessage as ChatMessageType,
  ChatRole,
  StructuredResponseData,
  KeyFactor,
  SourceCitation,
  ConfidenceLevel,
  ConversationSession,
} from "./state/useChatStore";

// Types
export type { FollowUpAction } from "./components/ClerkFollowUpBar";
export type { DiffSection, SectionDecision } from "./components/AIDiffView";
export type { ConversationContext } from "./hooks/useConversationContext";
export type { HistorySearchResult } from "./hooks/useClerkHistory";
