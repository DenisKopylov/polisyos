import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Button } from "@/shared/ui";
import { AuthoredText } from "@/shared/ui/authored-text";
import type { ChatMessage as ChatMessageType } from "../state/useChatStore";
import { ChatStreamIndicator } from "./ChatStreamIndicator";
import { ClerkStructuredResponse } from "./ClerkStructuredResponse";
import { ClerkProgressiveStream } from "./ClerkProgressiveStream";
import { ClerkSuggestionChips } from "./ClerkSuggestionChips";
import { AIDiffView } from "./AIDiffView";

type ChatMessageProps = {
  message: ChatMessageType;
  isStreaming: boolean;
  onSuggestionSelect?: (question: string) => void;
};

const STATUS_LABEL_MAP: Record<string, string> = {
  running: "clerk.statusPlanning",
  planning: "clerk.statusPlanning",
  collecting: "clerk.statusCollecting",
  simulating: "clerk.statusSimulating",
  governance: "clerk.statusGovernance",
  completed: "clerk.statusComplete",
  failed: "clerk.statusFailed",
};

function RunStatusBadge({ status }: { status: string }) {
  const kind =
    status === "completed"
      ? "ok"
      : status === "failed" || status === "rejected"
        ? "fail"
        : "info";
  return <Badge kind={kind}>{status}</Badge>;
}

export function ChatMessage({
  message,
  isStreaming,
  onSuggestionSelect,
}: ChatMessageProps) {
  const { t } = useI18n();
  const isUser = message.role === "user";
  const authoredTimestamp = new Date(message.timestamp).toISOString();

  return (
    <div
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-[var(--radius-card)] px-5 py-4",
          isUser
            ? "bg-[var(--teal-soft)] text-[var(--ink)]"
            : "panel text-[var(--ink)]",
        )}
      >
        {isUser ? (
          <AuthoredText
            author="human"
            className="text-[16px] leading-relaxed whitespace-pre-wrap"
            timestamp={authoredTimestamp}
          >
            {message.content}
          </AuthoredText>
        ) : (
          <div className="flex flex-col gap-3">
            {message.runStatus && (
              <div className="flex items-center gap-3">
                <RunStatusBadge status={message.runStatus} />
                <span className="text-sm text-[var(--slate)]">
                  {t(
                    STATUS_LABEL_MAP[message.runStatus] ??
                      "clerk.statusPlanning",
                  )}
                </span>
              </div>
            )}

            {/* Progressive streaming with typewriter effect */}
            {message.isProgressive && message.streamedTokens != null && (
              <ClerkProgressiveStream
                streamedTokens={message.streamedTokens}
                statusChips={message.structured?.statusChips}
                isActive={isStreaming}
                timestamp={message.timestamp}
              />
            )}

            {/* Old-style streaming dots (fallback) */}
            {isStreaming &&
              !message.error &&
              !message.isProgressive &&
              !message.content &&
              !message.structured && <ChatStreamIndicator />}

            {message.error && (
              <AuthoredText
                author="critic"
                className="text-sm text-[var(--danger)]"
                timestamp={authoredTimestamp}
              >
                {message.error}
              </AuthoredText>
            )}

            {/* Structured response card */}
            {message.structured &&
              !message.isProgressive &&
              (message.structured.verdict ||
                message.structured.keyFactors ||
                message.structured.confidence != null) && (
                <ClerkStructuredResponse
                  data={message.structured}
                  timestamp={message.timestamp}
                />
              )}

            {/* AI Diff View */}
            {message.structured?.diff && message.structured.diff.length > 0 && (
              <AIDiffView sections={message.structured.diff} />
            )}

            {/* Plain content (when no structured data) */}
            {message.content &&
              !message.error &&
              !message.isProgressive &&
              !message.structured?.verdict && (
                <AuthoredText
                  author="drafter"
                  className="text-sm leading-relaxed"
                  timestamp={authoredTimestamp}
                >
                  {message.content}
                </AuthoredText>
              )}

            {/* View full analysis link */}
            {message.runId &&
              (message.runStatus === "completed" ||
                message.runStatus === "failed") && (
                <div className="pt-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    to={`/runs/${message.runId}`}
                  >
                    {t("clerk.viewFullAnalysis")}
                  </Button>
                </div>
              )}

            {/* Suggestion chips at the end of completed responses */}
            {!isStreaming &&
              message.structured?.suggestions &&
              message.structured.suggestions.length > 0 &&
              onSuggestionSelect && (
                <ClerkSuggestionChips
                  suggestions={message.structured.suggestions}
                  onSelect={onSuggestionSelect}
                  className="pt-1"
                />
              )}
          </div>
        )}
      </div>
    </div>
  );
}
