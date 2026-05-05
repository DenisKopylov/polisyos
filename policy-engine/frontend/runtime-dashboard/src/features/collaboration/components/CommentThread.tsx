import { useCallback, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CheckCircle2, CornerDownRight, Send } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Button, Card } from "@/shared/ui/primitives";
import { fadeInUp, staggerContainer } from "@/shared/ui/motion";

import { useComments } from "../hooks/useComments";
import type { Comment, CommentDraft } from "../types";

type CommentThreadProps = {
  sessionId: string;
  anchorId: string;
  anchorType: Comment["anchorType"];
  className?: string;
};

type SingleCommentProps = {
  comment: Comment;
  isReply?: boolean;
  onReply?: () => void;
  onResolve?: (commentId: string) => void;
  canResolve?: boolean;
};

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60_000);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

function SingleComment({
  comment,
  isReply,
  onReply,
  onResolve,
  canResolve,
}: SingleCommentProps) {
  const { t } = useI18n();

  return (
    <motion.div
      variants={fadeInUp}
      className={cn("group flex gap-2.5", isReply && "ml-6")}
    >
      {/* Author avatar */}
      <div
        className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white"
        style={{ backgroundColor: comment.authorAccentColor }}
      >
        {comment.authorName.slice(0, 2).toUpperCase()}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold">{comment.authorName}</span>
          <span className="text-muted text-[11px]">
            {formatRelativeTime(comment.createdAt)}
          </span>
          {comment.resolvedAt && (
            <span className="text-[11px] font-medium text-emerald-600">
              {t("collaboration.comments.resolved")}
            </span>
          )}
        </div>
        <p
          className={cn(
            "mt-0.5 text-sm leading-relaxed",
            comment.resolvedAt && "text-muted line-through",
          )}
        >
          {comment.body}
        </p>

        {/* Actions */}
        <div className="mt-1 flex gap-2 opacity-0 transition-opacity group-hover:opacity-100">
          {onReply && !comment.resolvedAt && (
            <button
              type="button"
              className="text-muted hover:text-foreground flex items-center gap-1 text-[11px] font-medium"
              onClick={onReply}
            >
              <CornerDownRight className="h-3 w-3" />
              {t("collaboration.comments.reply")}
            </button>
          )}
          {canResolve && !comment.resolvedAt && onResolve && (
            <button
              type="button"
              className="flex items-center gap-1 text-[11px] font-medium text-emerald-600 hover:text-emerald-700"
              onClick={() => onResolve(comment.id)}
            >
              <CheckCircle2 className="h-3 w-3" />
              {t("collaboration.comments.resolve")}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function CommentComposer({
  onSubmit,
  placeholder,
  isSubmitting,
}: {
  onSubmit: (body: string) => void;
  placeholder: string;
  isSubmitting: boolean;
}) {
  const [body, setBody] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const trimmed = body.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setBody("");
    inputRef.current?.focus();
  }, [body, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <div className="border-line flex gap-2 border-t pt-3">
      <textarea
        ref={inputRef}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={2}
        className="bg-surface placeholder:text-muted border-line focus:ring-accent/40 min-h-[2.5rem] flex-1 resize-none rounded-xl border px-3 py-2 text-sm outline-none focus:ring-2"
      />
      <Button
        type="button"
        variant="primary"
        size="sm"
        onClick={handleSubmit}
        disabled={!body.trim() || isSubmitting}
        className="self-end"
      >
        <Send className="h-4 w-4" />
      </Button>
    </div>
  );
}

export function CommentThread({
  sessionId,
  anchorId,
  anchorType,
  className,
}: CommentThreadProps) {
  const { t } = useI18n();
  const { threads, addComment, resolveComment, isAdding } = useComments({
    sessionId,
    anchorId,
  });
  const [replyingTo, setReplyingTo] = useState<string | null>(null);

  const handleNewComment = useCallback(
    (body: string) => {
      const draft: CommentDraft = { body, anchorId, anchorType };
      addComment(draft);
    },
    [addComment, anchorId, anchorType],
  );

  const handleReply = useCallback(
    (parentId: string, body: string) => {
      const draft: CommentDraft = {
        body,
        anchorId,
        anchorType,
        parentId,
      };
      addComment(draft);
      setReplyingTo(null);
    },
    [addComment, anchorId, anchorType],
  );

  return (
    <Card className={cn("flex flex-col gap-3", className)}>
      <h4 className="text-sm font-semibold">
        {t("collaboration.comments.title")}
        {threads.length > 0 && (
          <span className="text-muted ml-1 font-normal">
            ({threads.length})
          </span>
        )}
      </h4>

      {threads.length === 0 && (
        <p className="text-muted py-4 text-center text-sm">
          {t("collaboration.comments.empty")}
        </p>
      )}

      <motion.div
        variants={staggerContainer()}
        initial="hidden"
        animate="visible"
        className="flex flex-col gap-4"
      >
        <AnimatePresence>
          {threads.map(({ root, replies, isResolved }) => (
            <motion.div
              key={root.id}
              variants={fadeInUp}
              className={cn(
                "border-line rounded-xl border p-3",
                isResolved && "opacity-60",
              )}
            >
              <SingleComment
                comment={root}
                onReply={() => setReplyingTo(root.id)}
                onResolve={resolveComment}
                canResolve={!isResolved}
              />

              {replies.map((reply) => (
                <div key={reply.id} className="mt-2">
                  <SingleComment comment={reply} isReply />
                </div>
              ))}

              {replyingTo === root.id && (
                <div className="mt-2 ml-6">
                  <CommentComposer
                    onSubmit={(body) => handleReply(root.id, body)}
                    placeholder={t("collaboration.comments.replyPlaceholder")}
                    isSubmitting={isAdding}
                  />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>

      <CommentComposer
        onSubmit={handleNewComment}
        placeholder={t("collaboration.comments.placeholder")}
        isSubmitting={isAdding}
      />
    </Card>
  );
}
