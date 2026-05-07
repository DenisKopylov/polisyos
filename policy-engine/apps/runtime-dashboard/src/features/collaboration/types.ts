// ---------------------------------------------------------------------------
// Collaboration feature domain types
// ---------------------------------------------------------------------------

/** A participant in a collaboration session. */
export type CollaborationParticipant = {
  accentColor: string;
  avatarUrl?: string;
  displayName: string;
  isOnline: boolean;
  isSelf: boolean;
  lastSeenAt: string;
  participantId: string;
  role: "editor" | "viewer";
};

/** Cursor position broadcast by a participant. */
export type CollaborationCursor = {
  accentColor: string;
  displayName: string;
  participantId: string;
  updatedAt: string;
  x: number;
  y: number;
};

/** A comment attached to an artifact or section. */
export type Comment = {
  id: string;
  authorId: string;
  authorName: string;
  authorAccentColor: string;
  body: string;
  createdAt: string;
  updatedAt?: string;
  resolvedAt?: string;
  resolvedBy?: string;
  /** Artifact or section this comment is attached to. */
  anchorId: string;
  anchorType: "artifact" | "chart" | "evidence" | "governance" | "section";
  /** Optional pixel / percentage coordinates within the anchor. */
  anchorPosition?: { x: number; y: number };
  parentId?: string;
};

/** A new comment being submitted (before server assigns id). */
export type CommentDraft = Pick<
  Comment,
  "body" | "anchorId" | "anchorType" | "anchorPosition" | "parentId"
>;

/** Activity feed event from the team. */
export type ActivityEvent = {
  id: string;
  type: ActivityEventType;
  actorId: string;
  actorName: string;
  actorAccentColor: string;
  /** Human-readable summary (server-generated). */
  summary: string;
  /** Optional linked entity. */
  targetId?: string;
  targetType?: "artifact" | "comment" | "evidence" | "run" | "scenario";
  /** Optional extra payload for UI rendering. */
  metadata?: Record<string, unknown>;
  occurredAt: string;
};

export type ActivityEventType =
  | "comment.added"
  | "comment.resolved"
  | "evidence.promoted"
  | "governance.passed"
  | "governance.failed"
  | "review.submitted"
  | "run.completed"
  | "run.failed"
  | "run.started"
  | "scenario.modified"
  | "share.created";

/** Share link configuration. */
export type ShareConfig = {
  /** Who can access: anyone with link, or specific users. */
  access: "link" | "restricted";
  /** Permission level for link-based access. */
  linkPermission: "edit" | "view";
  /** Specific user IDs for restricted access. */
  allowedUserIds: string[];
  /** Expiration (ISO string, optional). */
  expiresAt?: string;
};

/** Collaboration session state. */
export type CollaborationSessionStatus =
  | "connected"
  | "connecting"
  | "disconnected"
  | "reconnecting";
