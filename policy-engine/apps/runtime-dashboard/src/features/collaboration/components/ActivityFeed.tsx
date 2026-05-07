import { AnimatePresence, motion } from "motion/react";
import {
  GitBranch,
  CheckCircle2,
  XCircle,
  MessageSquare,
  Shield,
  Play,
  Award,
  Share2,
  Pencil,
  AlertTriangle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Card, ScrollArea } from "@/shared/ui/primitives";
import { fadeInUp, staggerContainer } from "@/shared/ui/motion";

import { useActivityFeed } from "../hooks/useActivityFeed";
import type { ActivityEvent, ActivityEventType } from "../types";

type ActivityFeedProps = {
  sessionId: string;
  className?: string;
};

type ActivityItemProps = {
  event: ActivityEvent;
};

const EVENT_CONFIG: Record<
  ActivityEventType,
  { color: string; Icon: LucideIcon }
> = {
  "run.started": { color: "text-teal-500", Icon: Play },
  "run.completed": { color: "text-emerald-500", Icon: CheckCircle2 },
  "run.failed": { color: "text-red-500", Icon: XCircle },
  "comment.added": { color: "text-blue-500", Icon: MessageSquare },
  "comment.resolved": { color: "text-emerald-500", Icon: CheckCircle2 },
  "evidence.promoted": { color: "text-amber-500", Icon: Award },
  "governance.passed": { color: "text-emerald-500", Icon: Shield },
  "governance.failed": { color: "text-red-500", Icon: AlertTriangle },
  "review.submitted": { color: "text-violet-500", Icon: GitBranch },
  "scenario.modified": { color: "text-orange-500", Icon: Pencil },
  "share.created": { color: "text-indigo-500", Icon: Share2 },
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

function ActivityItem({ event }: ActivityItemProps) {
  const config = EVENT_CONFIG[event.type] ?? {
    color: "text-neutral-500",
    Icon: GitBranch,
  };
  const { Icon } = config;

  return (
    <motion.div variants={fadeInUp} className="flex items-start gap-3 py-2">
      {/* Icon */}
      <div
        className={cn(
          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-current/10",
          config.color,
        )}
      >
        <Icon className="h-3.5 w-3.5" />
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <p className="text-sm leading-snug">
          <span
            className="font-semibold"
            style={{ color: event.actorAccentColor }}
          >
            {event.actorName}
          </span>{" "}
          <span className="text-muted">{event.summary}</span>
        </p>
        <span className="text-muted text-[11px]">
          {formatRelativeTime(event.occurredAt)}
        </span>
      </div>
    </motion.div>
  );
}

export function ActivityFeed({ sessionId, className }: ActivityFeedProps) {
  const { t } = useI18n();
  const { events, isLoading } = useActivityFeed({ sessionId });

  return (
    <Card className={cn("flex flex-col", className)}>
      <div className="flex items-center justify-between pb-2">
        <h4 className="text-sm font-semibold">
          {t("collaboration.activity.title")}
        </h4>
        {isLoading && (
          <span className="text-muted animate-pulse text-xs">
            {t("common.loading")}
          </span>
        )}
      </div>

      {events.length === 0 && !isLoading && (
        <p className="text-muted py-6 text-center text-sm">
          {t("collaboration.activity.empty")}
        </p>
      )}

      <ScrollArea className="max-h-80">
        <motion.div
          variants={staggerContainer()}
          initial="hidden"
          animate="visible"
          className="divide-line divide-y"
        >
          <AnimatePresence>
            {events.map((event) => (
              <ActivityItem key={event.id} event={event} />
            ))}
          </AnimatePresence>
        </motion.div>
      </ScrollArea>
    </Card>
  );
}
