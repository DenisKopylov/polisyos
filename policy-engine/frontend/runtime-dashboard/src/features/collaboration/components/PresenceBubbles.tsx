import { AnimatePresence, motion } from "motion/react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/ui/primitives";
import { fadeInScale, transition } from "@/shared/ui/motion";

import type { CollaborationParticipant } from "../types";

type PresenceBubblesProps = {
  participants: CollaborationParticipant[];
  /** Max avatars to show before "+N" overflow. */
  maxVisible?: number;
  className?: string;
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function AvatarBubble({
  participant,
}: {
  participant: CollaborationParticipant;
}) {
  const { t } = useI18n();

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.div
          layout
          variants={fadeInScale}
          initial="hidden"
          animate="visible"
          exit="exit"
          className={cn(
            "relative flex h-8 w-8 items-center justify-center rounded-full border-2 border-white text-xs font-semibold text-white shadow-sm dark:border-neutral-900",
            participant.isSelf && "ring-accent/50 ring-2",
          )}
          style={{ backgroundColor: participant.accentColor }}
        >
          {participant.avatarUrl ? (
            <img
              src={participant.avatarUrl}
              alt={participant.displayName}
              className="h-full w-full rounded-full object-cover"
            />
          ) : (
            initials(participant.displayName)
          )}
          {/* Online indicator */}
          <span
            className={cn(
              "absolute -right-0.5 -bottom-0.5 h-2.5 w-2.5 rounded-full border-2 border-white dark:border-neutral-900",
              participant.isOnline ? "bg-emerald-500" : "bg-neutral-400",
            )}
          />
        </motion.div>
      </TooltipTrigger>
      <TooltipContent>
        <p className="font-semibold">
          {participant.isSelf
            ? t("collaboration.presence.you")
            : participant.displayName}
        </p>
        <p className="text-muted text-[11px]">
          {participant.isOnline
            ? t("collaboration.presence.online")
            : t("collaboration.presence.offline")}
          {" · "}
          {participant.role === "editor"
            ? t("collaboration.presence.editor")
            : t("collaboration.presence.viewer")}
        </p>
      </TooltipContent>
    </Tooltip>
  );
}

export function PresenceBubbles({
  participants,
  maxVisible = 5,
  className,
}: PresenceBubblesProps) {
  const { t } = useI18n();
  const online = participants.filter((p) => p.isOnline);
  const visible = online.slice(0, maxVisible);
  const overflow = online.length - maxVisible;

  return (
    <div
      className={cn("flex items-center -space-x-2", className)}
      aria-label={t("collaboration.presence.activeUsers", {
        count: String(online.length),
      })}
    >
      <AnimatePresence mode="popLayout">
        {visible.map((participant) => (
          <AvatarBubble
            key={participant.participantId}
            participant={participant}
          />
        ))}
      </AnimatePresence>

      {overflow > 0 && (
        <motion.div
          layout
          transition={transition.moderate}
          className="bg-muted text-muted-foreground flex h-8 w-8 items-center justify-center rounded-full border-2 border-white text-xs font-semibold dark:border-neutral-900"
        >
          +{overflow}
        </motion.div>
      )}
    </div>
  );
}
