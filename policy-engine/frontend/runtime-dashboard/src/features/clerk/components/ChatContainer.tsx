import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { Button } from "@/shared/ui";
import { useChatStore } from "../state/useChatStore";
import { useClerkNlRun } from "../hooks/useClerkNlRun";
import { useConversationContext } from "../hooks/useConversationContext";
import { ChatInput } from "./ChatInput";
import { ChatMessage } from "./ChatMessage";
import { ClerkFollowUpBar } from "./ClerkFollowUpBar";
import { ExportConversation } from "./ExportConversation";
import { ConversationHistorySearch } from "./ConversationHistorySearch";

export function ChatContainer() {
  const { t } = useI18n();
  const { messages, isStreaming } = useChatStore();
  const { submit, isLoading } = useClerkNlRun();
  const ctx = useConversationContext();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isStreaming]);

  const handleSuggestionSelect = (question: string) => {
    submit(question);
  };

  // Build follow-up actions from context
  const followUpActions = ctx.contextualSuggestions.slice(0, 3).map((s) => ({
    label: s.length > 40 ? s.slice(0, 40) + "..." : s,
    value: s,
  }));

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-[var(--radius-panel)] panel">
      {/* Top bar: history + export */}
      <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-2">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowHistory(!showHistory)}
          >
            {t("clerk.history")}
          </Button>
        </div>
        <ExportConversation />
      </div>

      {/* History panel (slides in) */}
      {showHistory && (
        <div className="border-b border-[var(--line)] bg-[var(--panel)] px-5 py-4">
          <ConversationHistorySearch onClose={() => setShowHistory(false)} />
        </div>
      )}

      {/* Messages */}
      <div
        className="flex flex-1 flex-col gap-4 overflow-y-auto px-5 py-6"
        role="log"
        aria-live="polite"
      >
        {messages.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <h2 className="text-xl font-bold text-[var(--ink)]">
              {t("clerk.welcomeTitle")}
            </h2>
            <p className="max-w-[480px] text-sm leading-relaxed text-[var(--slate)]">
              {t("clerk.welcomeSubtitle")}
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            isStreaming={
              isStreaming && msg.role === "system" && i === messages.length - 1
            }
            onSuggestionSelect={handleSuggestionSelect}
          />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Follow-up bar (shown after completed responses) */}
      {!isStreaming && messages.length > 0 && followUpActions.length > 0 && (
        <ClerkFollowUpBar
          actions={followUpActions}
          onAction={handleSuggestionSelect}
        />
      )}

      <ChatInput onSubmit={submit} disabled={isLoading} />
    </div>
  );
}
