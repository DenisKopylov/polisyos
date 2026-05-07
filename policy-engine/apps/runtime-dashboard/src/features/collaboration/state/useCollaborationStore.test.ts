import { beforeEach, describe, expect, it } from "vitest";

import { useCollaborationStore } from "./useCollaborationStore";

describe("useCollaborationStore", () => {
  beforeEach(() => {
    useCollaborationStore.getState().reset();
  });

  it("merges comment snapshots without overwriting newer realtime updates", () => {
    const store = useCollaborationStore.getState();
    store.setSessionId("session-1");

    store.addComment({
      anchorId: "anchor-1",
      anchorType: "section",
      authorAccentColor: "#000000",
      authorId: "user-1",
      authorName: "Analyst",
      body: "Realtime body",
      createdAt: "2026-04-08T10:00:00Z",
      id: "comment-1",
      updatedAt: "2026-04-08T11:00:00Z",
    });

    store.hydrateCommentsSnapshot("session-1", [
      {
        anchorId: "anchor-1",
        anchorType: "section",
        authorAccentColor: "#000000",
        authorId: "user-1",
        authorName: "Analyst",
        body: "Older snapshot body",
        createdAt: "2026-04-08T10:00:00Z",
        id: "comment-1",
        updatedAt: "2026-04-08T10:30:00Z",
      },
      {
        anchorId: "anchor-1",
        anchorType: "section",
        authorAccentColor: "#123456",
        authorId: "user-2",
        authorName: "Reviewer",
        body: "Snapshot reply",
        createdAt: "2026-04-08T10:15:00Z",
        id: "comment-2",
        parentId: "comment-1",
      },
    ]);

    expect(useCollaborationStore.getState().comments).toEqual([
      expect.objectContaining({
        body: "Realtime body",
        id: "comment-1",
        updatedAt: "2026-04-08T11:00:00Z",
      }),
      expect.objectContaining({
        body: "Snapshot reply",
        id: "comment-2",
      }),
    ]);
  });

  it("ignores comment and activity snapshots from stale sessions", () => {
    const store = useCollaborationStore.getState();
    store.setSessionId("session-2");

    store.hydrateCommentsSnapshot("session-1", [
      {
        anchorId: "anchor-1",
        anchorType: "section",
        authorAccentColor: "#000000",
        authorId: "user-1",
        authorName: "Analyst",
        body: "Stale snapshot",
        createdAt: "2026-04-08T10:00:00Z",
        id: "comment-stale",
      },
    ]);
    store.hydrateActivitySnapshot("session-1", [
      {
        actorAccentColor: "#000000",
        actorId: "user-1",
        actorName: "Analyst",
        id: "activity-stale",
        occurredAt: "2026-04-08T10:00:00Z",
        summary: "Stale activity",
        type: "comment.added",
      },
    ]);

    expect(useCollaborationStore.getState().comments).toEqual([]);
    expect(useCollaborationStore.getState().activity).toEqual([]);
  });

  it("deduplicates and orders activity using latest event freshness", () => {
    const store = useCollaborationStore.getState();
    store.setSessionId("session-3");

    store.prependActivity({
      actorAccentColor: "#111111",
      actorId: "user-1",
      actorName: "Reviewer",
      id: "activity-1",
      occurredAt: "2026-04-08T11:00:00Z",
      summary: "Realtime event",
      type: "review.submitted",
    });

    store.hydrateActivitySnapshot("session-3", [
      {
        actorAccentColor: "#111111",
        actorId: "user-1",
        actorName: "Reviewer",
        id: "activity-1",
        occurredAt: "2026-04-08T10:00:00Z",
        summary: "Older snapshot event",
        type: "review.submitted",
      },
      {
        actorAccentColor: "#222222",
        actorId: "user-2",
        actorName: "Operator",
        id: "activity-2",
        occurredAt: "2026-04-08T09:00:00Z",
        summary: "Snapshot event",
        type: "run.completed",
      },
    ]);

    expect(useCollaborationStore.getState().activity).toEqual([
      expect.objectContaining({
        id: "activity-1",
        occurredAt: "2026-04-08T11:00:00Z",
        summary: "Realtime event",
      }),
      expect.objectContaining({
        id: "activity-2",
        summary: "Snapshot event",
      }),
    ]);
  });
});
