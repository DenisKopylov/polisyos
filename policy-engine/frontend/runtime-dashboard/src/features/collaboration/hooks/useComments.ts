import { useCallback, useEffect, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useCollaborationStore } from "../state/useCollaborationStore";
import type { Comment, CommentDraft } from "../types";

const COMMENTS_QUERY_KEY = ["collaboration", "comments"] as const;

type UseCommentsOptions = {
  sessionId?: string | null;
  anchorId?: string | null;
};

async function fetchComments(sessionId: string): Promise<Comment[]> {
  const response = await fetch(
    `/api/v1/collaboration/${sessionId}/comments`,
    { credentials: "include" },
  );
  if (!response.ok) return [];
  const data = await response.json();
  return (data.comments ?? []).map(mapServerComment);
}

async function postComment(
  sessionId: string,
  draft: CommentDraft,
): Promise<Comment> {
  const response = await fetch(
    `/api/v1/collaboration/${sessionId}/comments`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        body: draft.body,
        anchor_id: draft.anchorId,
        anchor_type: draft.anchorType,
        anchor_position: draft.anchorPosition,
        parent_id: draft.parentId,
      }),
    },
  );
  if (!response.ok) throw new Error("Failed to post comment");
  return mapServerComment(await response.json());
}

async function resolveCommentApi(
  sessionId: string,
  commentId: string,
): Promise<void> {
  const response = await fetch(
    `/api/v1/collaboration/${sessionId}/comments/${commentId}/resolve`,
    { method: "POST", credentials: "include" },
  );
  if (!response.ok) throw new Error("Failed to resolve comment");
}

function mapServerComment(raw: Record<string, unknown>): Comment {
  return {
    id: raw.id as string,
    authorId: (raw.author_id ?? "") as string,
    authorName: (raw.author_name ?? "") as string,
    authorAccentColor: (raw.author_accent_color ?? "#6B7280") as string,
    body: (raw.body ?? "") as string,
    createdAt: (raw.created_at ?? "") as string,
    updatedAt: raw.updated_at as string | undefined,
    resolvedAt: raw.resolved_at as string | undefined,
    resolvedBy: raw.resolved_by as string | undefined,
    anchorId: (raw.anchor_id ?? "") as string,
    anchorType: (raw.anchor_type ?? "section") as Comment["anchorType"],
    anchorPosition: raw.anchor_position as
      | { x: number; y: number }
      | undefined,
    parentId: raw.parent_id as string | undefined,
  };
}

/**
 * Provides comment data and mutations for a collaboration session.
 * Uses TanStack Query for initial fetch, then real-time updates via store.
 */
export function useComments({ sessionId, anchorId }: UseCommentsOptions) {
  const queryClient = useQueryClient();
  const storeComments = useCollaborationStore((s) => s.comments);
  const setSessionId = useCollaborationStore((s) => s.setSessionId);
  const hydrateCommentsSnapshot = useCollaborationStore(
    (s) => s.hydrateCommentsSnapshot,
  );

  useEffect(() => {
    setSessionId(sessionId ?? null);
  }, [sessionId, setSessionId]);

  // Initial fetch — seeds the store, then real-time takes over
  const { isLoading } = useQuery({
    queryKey: [...COMMENTS_QUERY_KEY, sessionId],
    queryFn: async () => {
      if (!sessionId) return [];
      const comments = await fetchComments(sessionId);
      hydrateCommentsSnapshot(sessionId, comments);
      return comments;
    },
    enabled: Boolean(sessionId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  // Filter by anchor if provided
  const comments = useMemo(() => {
    if (!anchorId) return storeComments;
    return storeComments.filter((c) => c.anchorId === anchorId);
  }, [storeComments, anchorId]);

  // Separate into threads: top-level comments and their replies
  const threads = useMemo(() => {
    const topLevel = comments.filter((c) => !c.parentId);
    return topLevel.map((root) => ({
      root,
      replies: comments
        .filter((c) => c.parentId === root.id)
        .sort(
          (a, b) =>
            new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
        ),
      isResolved: Boolean(root.resolvedAt),
    }));
  }, [comments]);

  const unresolvedCount = useMemo(
    () => threads.filter((t) => !t.isResolved).length,
    [threads],
  );

  // Add comment mutation
  const addMutation = useMutation({
    mutationFn: (draft: CommentDraft) => {
      if (!sessionId) throw new Error("No session");
      return postComment(sessionId, draft);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [...COMMENTS_QUERY_KEY, sessionId],
      });
    },
  });

  // Resolve comment mutation
  const resolveMutation = useMutation({
    mutationFn: (commentId: string) => {
      if (!sessionId) throw new Error("No session");
      return resolveCommentApi(sessionId, commentId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [...COMMENTS_QUERY_KEY, sessionId],
      });
    },
  });

  const addComment = useCallback(
    (draft: CommentDraft) => addMutation.mutate(draft),
    [addMutation],
  );

  const resolveComment = useCallback(
    (commentId: string) => resolveMutation.mutate(commentId),
    [resolveMutation],
  );

  return {
    comments,
    threads,
    unresolvedCount,
    isLoading,
    addComment,
    resolveComment,
    isAdding: addMutation.isPending,
    isResolving: resolveMutation.isPending,
  };
}
