import { useEffect, useState } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { Badge } from "@/shared/ui/primitives";
import { AuthoredText } from "@/shared/ui/authored-text";

type ClerkProgressiveStreamProps = {
  /** Tokens accumulated so far. */
  streamedTokens: string;
  /** Status chips to show during streaming. */
  statusChips?: string[];
  /** Whether still streaming. */
  isActive: boolean;
  className?: string;
  timestamp?: number;
};

const STAGE_ICONS: Record<string, string> = {
  planning: "\uD83D\uDCCB",
  collecting: "\uD83D\uDCE5",
  simulating: "\u2699\uFE0F",
  governance: "\uD83D\uDEE1\uFE0F",
};

function StatusChip({ label }: { label: string }) {
  const icon = Object.entries(STAGE_ICONS).find(([key]) =>
    label.toLowerCase().includes(key),
  )?.[1];

  return (
    <Badge kind="info" className="gap-1">
      {icon && <span aria-hidden="true">{icon}</span>}
      {label}
    </Badge>
  );
}

export function ClerkProgressiveStream({
  streamedTokens,
  statusChips,
  isActive,
  className,
  timestamp,
}: ClerkProgressiveStreamProps) {
  const { t } = useI18n();
  const [displayedLength, setDisplayedLength] = useState(0);
  const authoredTimestamp =
    typeof timestamp === "number"
      ? new Date(timestamp).toISOString()
      : undefined;

  // Typewriter effect: reveal tokens progressively
  useEffect(() => {
    if (!isActive && displayedLength >= streamedTokens.length) return;

    if (displayedLength < streamedTokens.length) {
      const batchSize = Math.min(3, streamedTokens.length - displayedLength);
      const timer = setTimeout(
        () => setDisplayedLength((prev) => prev + batchSize),
        16, // ~60fps
      );
      return () => clearTimeout(timer);
    }
  }, [displayedLength, streamedTokens.length, isActive]);

  // Jump to full text when streaming ends
  useEffect(() => {
    if (!isActive) {
      setDisplayedLength(streamedTokens.length);
    }
  }, [isActive, streamedTokens.length]);

  const displayed = streamedTokens.slice(0, displayedLength);

  return (
    <div className={cn("space-y-2", className)}>
      {/* Status chips */}
      {statusChips && statusChips.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {statusChips.map((chip, i) => (
            <StatusChip key={i} label={chip} />
          ))}
        </div>
      )}

      {/* Progressive text */}
      {displayed && (
        <AuthoredText
          as="div"
          author="drafter"
          className="text-sm leading-relaxed whitespace-pre-wrap"
          timestamp={authoredTimestamp}
        >
          {displayed}
          {isActive && (
            <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-[var(--teal)]" />
          )}
        </AuthoredText>
      )}

      {/* Pulsing dots when no text yet */}
      {isActive && !displayed && (
        <div
          className="flex items-center gap-1.5 py-1"
          aria-label={t("clerk.processing")}
        >
          <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--teal)]" />
          <span
            className="h-2 w-2 animate-pulse rounded-full bg-[var(--teal)]"
            style={{ animationDelay: "150ms" }}
          />
          <span
            className="h-2 w-2 animate-pulse rounded-full bg-[var(--teal)]"
            style={{ animationDelay: "300ms" }}
          />
        </div>
      )}
    </div>
  );
}
