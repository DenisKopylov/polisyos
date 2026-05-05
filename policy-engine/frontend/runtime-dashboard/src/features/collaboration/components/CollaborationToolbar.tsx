import { MessageSquare, Activity, Share2, Wifi, WifiOff } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  Badge,
  Button,
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/ui/primitives";

import { useCollaborationStore } from "../state/useCollaborationStore";
import { usePresence } from "../hooks/usePresence";
import { useComments } from "../hooks/useComments";
import { PresenceBubbles } from "./PresenceBubbles";

type CollaborationToolbarProps = {
  sessionId?: string | null;
  onShareClick?: () => void;
  className?: string;
};

function ConnectionIndicator() {
  const { t } = useI18n();
  const status = useCollaborationStore((s) => s.status);

  if (status === "connected") {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Wifi className="h-4 w-4 text-emerald-500" />
        </TooltipTrigger>
        <TooltipContent>{t("collaboration.toolbar.connected")}</TooltipContent>
      </Tooltip>
    );
  }

  if (status === "connecting" || status === "reconnecting") {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Wifi className="h-4 w-4 animate-pulse text-amber-500" />
        </TooltipTrigger>
        <TooltipContent>{t("collaboration.toolbar.connecting")}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <WifiOff className="h-4 w-4 text-neutral-400" />
      </TooltipTrigger>
      <TooltipContent>{t("collaboration.toolbar.disconnected")}</TooltipContent>
    </Tooltip>
  );
}

export function CollaborationToolbar({
  sessionId,
  onShareClick,
  className,
}: CollaborationToolbarProps) {
  const { t } = useI18n();
  const { all: participants, onlineCount } = usePresence();
  const { unresolvedCount } = useComments({ sessionId });
  const toggleComments = useCollaborationStore((s) => s.toggleCommentsPanel);
  const toggleActivity = useCollaborationStore((s) => s.toggleActivityPanel);
  const commentsPanelOpen = useCollaborationStore((s) => s.commentsPanelOpen);
  const activityPanelOpen = useCollaborationStore((s) => s.activityPanelOpen);

  return (
    <div
      className={cn(
        "bg-surface/80 border-line flex items-center gap-3 rounded-2xl border px-3 py-1.5 shadow-sm backdrop-blur-sm",
        className,
      )}
    >
      {/* Connection status */}
      <ConnectionIndicator />

      {/* Presence bubbles */}
      <PresenceBubbles participants={participants} maxVisible={4} />

      {onlineCount > 0 && (
        <span className="text-muted text-xs font-medium">
          {t("collaboration.toolbar.onlineCount", {
            count: String(onlineCount),
          })}
        </span>
      )}

      <div className="bg-line mx-1 h-5 w-px" />

      {/* Comments toggle */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant={commentsPanelOpen ? "secondary" : "ghost"}
            size="sm"
            onClick={toggleComments}
            className="relative"
          >
            <MessageSquare className="h-4 w-4" />
            {unresolvedCount > 0 && (
              <Badge
                kind="warn"
                className="absolute -top-1.5 -right-1.5 h-4 min-w-4 px-1 text-[10px]"
              >
                {unresolvedCount}
              </Badge>
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>{t("collaboration.toolbar.comments")}</TooltipContent>
      </Tooltip>

      {/* Activity toggle */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant={activityPanelOpen ? "secondary" : "ghost"}
            size="sm"
            onClick={toggleActivity}
          >
            <Activity className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>{t("collaboration.toolbar.activity")}</TooltipContent>
      </Tooltip>

      {/* Share button */}
      {onShareClick && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onShareClick}
            >
              <Share2 className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("collaboration.toolbar.share")}</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}
