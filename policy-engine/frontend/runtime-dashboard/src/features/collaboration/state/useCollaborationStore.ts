import { create } from "zustand";

import type {
  ActivityEvent,
  CollaborationCursor,
  CollaborationParticipant,
  CollaborationSessionStatus,
  Comment,
} from "../types";

const MAX_ACTIVITY_ITEMS = 200;

function parseIsoTimestamp(value?: string): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getCommentFreshness(comment: Comment): number {
  return Math.max(
    parseIsoTimestamp(comment.updatedAt),
    parseIsoTimestamp(comment.resolvedAt),
    parseIsoTimestamp(comment.createdAt),
  );
}

function mergeDefinedFields<T extends Record<string, unknown>>(
  base: T,
  patch: Partial<T>,
): T {
  const next = { ...base };
  for (const [key, value] of Object.entries(patch)) {
    if (value !== undefined) {
      next[key as keyof T] = value as T[keyof T];
    }
  }
  return next;
}

function mergeComments(existing: Comment, incoming: Comment): Comment {
  const existingFreshness = getCommentFreshness(existing);
  const incomingFreshness = getCommentFreshness(incoming);

  if (incomingFreshness >= existingFreshness) {
    return mergeDefinedFields(existing, incoming);
  }
  return mergeDefinedFields(incoming, existing);
}

function normalizeComments(comments: Comment[]): Comment[] {
  return [...comments].sort((left, right) => {
    const createdDiff =
      parseIsoTimestamp(left.createdAt) - parseIsoTimestamp(right.createdAt);
    if (createdDiff !== 0) {
      return createdDiff;
    }
    return left.id.localeCompare(right.id);
  });
}

function upsertComment(comments: Comment[], incoming: Comment): Comment[] {
  const existingIndex = comments.findIndex((comment) => comment.id === incoming.id);
  if (existingIndex === -1) {
    return normalizeComments([...comments, incoming]);
  }

  const next = [...comments];
  next[existingIndex] = mergeComments(next[existingIndex]!, incoming);
  return normalizeComments(next);
}

function getActivityFreshness(event: ActivityEvent): number {
  return parseIsoTimestamp(event.occurredAt);
}

function mergeActivityEvent(
  existing: ActivityEvent,
  incoming: ActivityEvent,
): ActivityEvent {
  if (getActivityFreshness(incoming) >= getActivityFreshness(existing)) {
    return mergeDefinedFields(existing, incoming);
  }
  return mergeDefinedFields(incoming, existing);
}

function normalizeActivity(events: ActivityEvent[]): ActivityEvent[] {
  return [...events]
    .sort((left, right) => {
      const freshnessDiff =
        getActivityFreshness(right) - getActivityFreshness(left);
      if (freshnessDiff !== 0) {
        return freshnessDiff;
      }
      return left.id.localeCompare(right.id);
    })
    .slice(0, MAX_ACTIVITY_ITEMS);
}

function upsertActivity(
  events: ActivityEvent[],
  incoming: ActivityEvent,
): ActivityEvent[] {
  const existingIndex = events.findIndex((event) => event.id === incoming.id);
  if (existingIndex === -1) {
    return normalizeActivity([incoming, ...events]);
  }

  const next = [...events];
  next[existingIndex] = mergeActivityEvent(next[existingIndex]!, incoming);
  return normalizeActivity(next);
}

type CollaborationState = {
  /** Current session ID. */
  sessionId: string | null;
  /** Connection status. */
  status: CollaborationSessionStatus;
  /** Active participants in the session. */
  participants: CollaborationParticipant[];
  /** Other participants' cursors (excludes self). */
  cursors: CollaborationCursor[];
  /** Comments for the current context. */
  comments: Comment[];
  /** Recent activity events. */
  activity: ActivityEvent[];
  /** Whether the comments panel is open. */
  commentsPanelOpen: boolean;
  /** Whether the activity panel is open. */
  activityPanelOpen: boolean;
  /** The anchor ID that is currently focused for commenting. */
  activeAnchorId: string | null;

  // Actions
  setSessionId: (id: string | null) => void;
  setStatus: (status: CollaborationSessionStatus) => void;
  setParticipants: (participants: CollaborationParticipant[]) => void;
  setCursors: (cursors: CollaborationCursor[]) => void;
  hydrateCommentsSnapshot: (sessionId: string, comments: Comment[]) => void;
  addComment: (comment: Comment) => void;
  updateComment: (comment: Comment) => void;
  resolveComment: (comment: Comment) => void;
  hydrateActivitySnapshot: (sessionId: string, events: ActivityEvent[]) => void;
  prependActivity: (event: ActivityEvent) => void;
  toggleCommentsPanel: () => void;
  toggleActivityPanel: () => void;
  setActiveAnchorId: (id: string | null) => void;
  reset: () => void;
};

const INITIAL: Pick<
  CollaborationState,
  | "sessionId"
  | "status"
  | "participants"
  | "cursors"
  | "comments"
  | "activity"
  | "commentsPanelOpen"
  | "activityPanelOpen"
  | "activeAnchorId"
> = {
  sessionId: null,
  status: "disconnected",
  participants: [],
  cursors: [],
  comments: [],
  activity: [],
  commentsPanelOpen: false,
  activityPanelOpen: false,
  activeAnchorId: null,
};

export const useCollaborationStore = create<CollaborationState>()((set) => ({
  ...INITIAL,

  setSessionId: (id) =>
    set((state) => {
      if (state.sessionId === id) {
        return { sessionId: id };
      }
      return {
        sessionId: id,
        participants: [],
        cursors: [],
        comments: [],
        activity: [],
      };
    }),
  setStatus: (status) => set({ status }),
  setParticipants: (participants) => set({ participants }),
  setCursors: (cursors) => set({ cursors }),

  hydrateCommentsSnapshot: (sessionId, comments) =>
    set((state) => {
      if (state.sessionId !== sessionId) {
        return state;
      }

      const merged = comments.reduce(
        (accumulator, comment) => upsertComment(accumulator, comment),
        state.comments,
      );
      return { comments: merged };
    }),
  addComment: (comment) =>
    set((state) => ({ comments: upsertComment(state.comments, comment) })),
  updateComment: (comment) =>
    set((state) => ({
      comments: upsertComment(state.comments, comment),
    })),
  resolveComment: (comment) =>
    set((state) => ({
      comments: upsertComment(state.comments, comment),
    })),

  hydrateActivitySnapshot: (sessionId, events) =>
    set((state) => {
      if (state.sessionId !== sessionId) {
        return state;
      }

      const merged = events.reduce(
        (accumulator, event) => upsertActivity(accumulator, event),
        state.activity,
      );
      return { activity: merged };
    }),
  prependActivity: (event) =>
    set((state) => ({
      activity: upsertActivity(state.activity, event),
    })),

  toggleCommentsPanel: () =>
    set((state) => ({ commentsPanelOpen: !state.commentsPanelOpen })),
  toggleActivityPanel: () =>
    set((state) => ({ activityPanelOpen: !state.activityPanelOpen })),
  setActiveAnchorId: (id) => set({ activeAnchorId: id }),

  reset: () => set(INITIAL),
}));
