import { useMemo } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { Badge } from "@/shared/ui";

export type ReviewCollaborator = {
  accentColor: string;
  displayName: string;
  isSelf: boolean;
  lastSeenAt: string;
  participantId: string;
  sessionCount: number;
};

export type ReviewCursor = {
  accentColor: string;
  displayName: string;
  participantId: string;
  updatedAt: string;
  x: number;
  y: number;
};

export type ReviewLease = {
  accentColor: string;
  acquiredAt: string;
  displayName: string;
  expiresAt: string;
  isSelf: boolean;
  participantId: string;
};

type ReviewPresenceSummaryProps = {
  participants: ReviewCollaborator[];
  status: "connecting" | "idle" | "live";
};

type ReviewLockNoticeProps = {
  lock: ReviewLease | null;
};

type ReviewCursorLayerProps = {
  cursors: ReviewCursor[];
};

function formatLeaseTime(rawValue: string) {
  const value = new Date(rawValue);
  if (Number.isNaN(value.getTime())) {
    return rawValue;
  }
  return value.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ReviewPresenceSummary({
  participants,
  status,
}: ReviewPresenceSummaryProps) {
  const { t } = useI18n();
  const summaryLabel =
    participants.length > 1
      ? t("panels.reviewCollaboration.reviewers", {
          count: String(participants.length),
        })
      : t("panels.reviewCollaboration.solo");

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge kind={status === "live" ? "info" : "warn"}>
        {status === "connecting"
          ? t("panels.reviewCollaboration.connecting")
          : t("panels.reviewCollaboration.live")}
      </Badge>
      <span className="text-muted text-xs font-semibold">{summaryLabel}</span>
      {participants.map((participant) => (
        <span
          key={`${participant.participantId}-${participant.sessionCount}`}
          className="border-line bg-surface/80 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold"
        >
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: participant.accentColor }}
          />
          <span>
            {participant.isSelf
              ? t("panels.reviewCollaboration.you")
              : participant.displayName}
          </span>
        </span>
      ))}
    </div>
  );
}

export function ReviewLockNotice({ lock }: ReviewLockNoticeProps) {
  const { t } = useI18n();

  if (!lock) {
    return null;
  }

  return (
    <div
      className={
        lock.isSelf
          ? "border-accent/20 bg-accent/8 text-accent rounded-2xl border px-3 py-2 text-sm"
          : "border-warning/30 bg-warning/5 text-warning rounded-2xl border px-3 py-2 text-sm"
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          aria-hidden="true"
          className="h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: lock.accentColor }}
        />
        <span className="font-semibold">
          {lock.isSelf
            ? t("panels.reviewCollaboration.lockOwned")
            : t("panels.reviewCollaboration.lockedBy", {
                name: lock.displayName,
              })}
        </span>
        <span className="text-xs opacity-80">
          {t("panels.reviewCollaboration.lockExpires", {
            time: formatLeaseTime(lock.expiresAt),
          })}
        </span>
      </div>
    </div>
  );
}

export function ReviewCursorLayer({ cursors }: ReviewCursorLayerProps) {
  const visibleCursors = useMemo(
    () =>
      cursors.filter(
        (cursor) => Number.isFinite(cursor.x) && Number.isFinite(cursor.y),
      ),
    [cursors],
  );

  if (visibleCursors.length === 0) {
    return null;
  }

  return (
    <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden">
      {visibleCursors.map((cursor) => (
        <div
          key={`${cursor.participantId}-${cursor.updatedAt}`}
          className="absolute"
          style={{
            left: `${cursor.x * 100}%`,
            top: `${cursor.y * 100}%`,
            transform: "translate(-6px, -6px)",
          }}
        >
          <div
            className="h-3 w-3 rounded-full border border-white shadow-sm"
            style={{ backgroundColor: cursor.accentColor }}
          />
          <div
            className="mt-1 rounded-full px-2 py-1 text-[10px] font-semibold text-white shadow"
            style={{ backgroundColor: cursor.accentColor }}
          >
            {cursor.displayName}
          </div>
        </div>
      ))}
    </div>
  );
}
