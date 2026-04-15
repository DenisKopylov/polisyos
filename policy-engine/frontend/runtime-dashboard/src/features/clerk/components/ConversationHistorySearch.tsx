import { cn, formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n/LocaleProvider";
import { Card, Button, Badge, Input } from "@/shared/ui/primitives";

import { useClerkHistory, type HistorySearchResult } from "../hooks/useClerkHistory";

type ConversationHistorySearchProps = {
  onClose?: () => void;
  className?: string;
};

function SessionCard({
  locale,
  t,
  result,
  onLoad,
  onDelete,
}: {
  locale: "en" | "uk";
  t: (path: string, vars?: Record<string, string | number>) => string;
  result: HistorySearchResult;
  onLoad: () => void;
  onDelete: () => void;
}) {
  const { session, matches } = result;
  const messageCount = session.messages.length;

  return (
    <Card className="p-3 transition-colors hover:bg-[var(--surface)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={onLoad}
            className="text-left"
          >
            <p className="truncate text-sm font-semibold text-[var(--ink)]">
              {session.title}
            </p>
          </button>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--slate)]">
            <span>{t("clerk.messageCount", { count: messageCount })}</span>
            <span>
              {formatDate(session.updatedAt, locale, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>

          {/* Search match snippets */}
          {matches.length > 0 && (
            <div className="mt-2 space-y-1">
              {matches.slice(0, 2).map((match) => (
                <div
                  key={match.messageId}
                  className="rounded-lg bg-[var(--surface)] px-2 py-1 text-xs text-[var(--slate)]"
                >
                  <Badge kind={match.role === "user" ? "info" : "neutral"} className="mr-1 text-[9px]">
                    {match.role}
                  </Badge>
                  {match.snippet}
                </div>
              ))}
              {matches.length > 2 && (
                <span className="text-xs text-[var(--slate)]">
                  {t("clerk.moreMatches", { count: matches.length - 2 })}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex shrink-0 gap-1">
          <Button type="button" variant="ghost" size="sm" onClick={onLoad}>
            {t("clerk.loadConversation")}
          </Button>
          <button
            type="button"
            onClick={onDelete}
            className="rounded-lg px-2 py-1 text-xs text-[var(--slate)] hover:text-[var(--danger)]"
            aria-label={t("clerk.deleteConversation")}
            title={t("clerk.deleteConversation")}
          >
            {"\u2715"}
          </button>
        </div>
      </div>
    </Card>
  );
}

export function ConversationHistorySearch({
  onClose,
  className,
}: ConversationHistorySearchProps) {
  const { locale, t } = useI18n();
  const {
    searchQuery,
    setSearchQuery,
    searchResults,
    loadSession,
    deleteSession,
    newSession,
    totalSessions,
  } = useClerkHistory();

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">{t("clerk.conversationHistory")}</h3>
          <Badge kind="neutral">{totalSessions}</Badge>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={newSession}>
            {t("clerk.newConversation")}
          </Button>
          {onClose && (
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              {t("common.close")}
            </Button>
          )}
        </div>
      </div>

      {/* Search */}
      <Input
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        placeholder={t("clerk.searchConversations")}
        className="text-sm"
      />

      {/* Results */}
      <div className="max-h-[60vh] space-y-2 overflow-y-auto">
        {searchResults.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--slate)]">
            {searchQuery
              ? t("clerk.noSearchResults")
              : t("clerk.noConversations")}
          </p>
        ) : (
          searchResults.map((result) => (
            <SessionCard
              key={result.session.id}
              locale={locale}
              t={t}
              result={result}
              onLoad={() => {
                loadSession(result.session.id);
                onClose?.();
              }}
              onDelete={() => deleteSession(result.session.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
