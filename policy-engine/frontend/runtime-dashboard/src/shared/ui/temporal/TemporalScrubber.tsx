import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Clock } from "lucide-react";
import { useParams } from "react-router-dom";

import {
  formatTemporalAnnouncement,
  formatTemporalDate,
  normalizeTemporalInstant,
  type TemporalEventPoint,
} from "@/app/providers/temporal-scope";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";
import { useMaybeReducedMotionPreference } from "@/shared/a11y";
import { Button } from "@/shared/ui/primitives";
import { cn } from "@/lib/utils";
import { TemporalCursorMarker } from "./TemporalCursorMarker";
import { TemporalLegend } from "./TemporalLegend";
import { useTemporalRange } from "./useTemporalRange";

type TemporalScrubberProps = {
  className?: string;
  labels?: Partial<typeof DEFAULT_LABELS>;
};

type TemporalCursor = NonNullable<ReturnType<typeof useMaybeTemporalCursor>>;

const DEFAULT_LABELS = {
  now: "Now",
  observed: "Observed",
  simulated: "Simulated",
  slider: "Temporal cursor",
};

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;
const MONTH = 30 * DAY;
const COMMIT_DELAY_MS = 150;
const ANNOUNCE_DELAY_MS = 500;

export function TemporalScrubber(props: TemporalScrubberProps) {
  const cursor = useMaybeTemporalCursor();
  if (!cursor) {
    return null;
  }
  return <TemporalScrubberInner {...props} cursor={cursor} />;
}

function TemporalScrubberInner({
  className,
  cursor,
  labels,
}: TemporalScrubberProps & { cursor: TemporalCursor }) {
  const params = useParams();
  const runId = params.runId ?? null;
  const mergedLabels = { ...DEFAULT_LABELS, ...labels };
  const { prefersReducedMotion } = useMaybeReducedMotionPreference();
  const [announcement, setAnnouncement] = useState("");
  const announceTimerRef = useRef<number | null>(null);
  const commitTimerRef = useRef<number | null>(null);
  const frameRef = useRef<number | null>(null);

  useTemporalRange(runId);

  useEffect(
    () => () => {
      if (commitTimerRef.current) {
        window.clearTimeout(commitTimerRef.current);
      }
      if (announceTimerRef.current) {
        window.clearTimeout(announceTimerRef.current);
      }
      if (frameRef.current) {
        window.cancelAnimationFrame(frameRef.current);
      }
    },
    [],
  );

  const range = cursor?.range;
  const txRange = cursor?.txRange;
  const earliest = range?.earliest ? new Date(range.earliest).getTime() : null;
  const latest = range?.latest ? new Date(range.latest).getTime() : null;
  const effectiveValidAt =
    cursor?.effectiveScope?.validAt ??
    range?.latest ??
    new Date().toISOString();
  const effectiveTxAt =
    cursor?.effectiveScope?.txAt ?? txRange?.latest ?? effectiveValidAt;
  const value = new Date(
    normalizeTemporalInstant(effectiveValidAt) ?? effectiveValidAt,
  ).getTime();
  const hasUsableRange =
    cursor !== null &&
    earliest !== null &&
    latest !== null &&
    Number.isFinite(earliest) &&
    Number.isFinite(latest) &&
    latest > earliest;

  const markerPosition = useMemo(() => {
    if (!hasUsableRange || earliest === null || latest === null) {
      return 1;
    }
    return (value - earliest) / (latest - earliest);
  }, [earliest, hasUsableRange, latest, value]);

  const announce = useCallback(
    (validAt: string, txAt: string | null | undefined) => {
      if (announceTimerRef.current) {
        window.clearTimeout(announceTimerRef.current);
      }
      announceTimerRef.current = window.setTimeout(() => {
        setAnnouncement(
          formatTemporalAnnouncement(
            {
              txAt,
              validAt,
            },
            navigator.language,
          ),
        );
      }, ANNOUNCE_DELAY_MS);
    },
    [],
  );

  const commitValue = useCallback(
    (nextValue: number) => {
      if (!cursor || !range) {
        return;
      }
      const validAt = snapIfNeeded(
        new Date(nextValue).toISOString(),
        cursor.eventPoints,
        prefersReducedMotion,
      );
      const nextScope = {
        ...(cursor.effectiveScope ?? {}),
        txAt: cursor.effectiveScope?.txAt ?? txRange?.latest ?? validAt,
        validAt,
      };
      cursor.setPreviewScope(nextScope);
      if (commitTimerRef.current) {
        window.clearTimeout(commitTimerRef.current);
      }
      commitTimerRef.current = window.setTimeout(() => {
        cursor.commitScope(nextScope);
        announce(validAt, nextScope.txAt);
      }, COMMIT_DELAY_MS);
    },
    [announce, cursor, prefersReducedMotion, range, txRange?.latest],
  );

  const schedulePreview = useCallback(
    (nextValue: number) => {
      if (frameRef.current) {
        window.cancelAnimationFrame(frameRef.current);
      }
      frameRef.current = window.requestAnimationFrame(() => {
        commitValue(nextValue);
      });
    },
    [commitValue],
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (!cursor || !hasUsableRange || earliest === null || latest === null) {
        return;
      }
      let amount = 0;
      if (event.key === "ArrowLeft") {
        amount = event.altKey ? -HOUR : event.shiftKey ? -WEEK : -DAY;
      } else if (event.key === "ArrowRight") {
        amount = event.altKey ? HOUR : event.shiftKey ? WEEK : DAY;
      } else if (event.key === "PageUp") {
        amount = MONTH;
      } else if (event.key === "PageDown") {
        amount = -MONTH;
      } else if (event.key === "Home") {
        event.preventDefault();
        commitValue(earliest);
        return;
      } else if (event.key === "End" || event.key.toLowerCase() === "n") {
        event.preventDefault();
        commitValue(latest);
        return;
      } else {
        return;
      }
      event.preventDefault();
      commitValue(value + amount);
    },
    [commitValue, cursor, earliest, hasUsableRange, latest, value],
  );

  if (!hasUsableRange || earliest === null || latest === null) {
    return null;
  }

  const valueText = formatTemporalAnnouncement(
    {
      txAt: effectiveTxAt,
      validAt: effectiveValidAt,
    },
    navigator.language,
  );

  return (
    <div
      className={cn("temporal-scrubber flex h-8 items-center gap-3", className)}
      data-testid="temporal-scrubber"
    >
      <div className="relative min-w-0 flex-1">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-1/2 h-px -translate-y-1/2 overflow-hidden rounded-full"
          style={{
            background:
              "linear-gradient(90deg, var(--chart-primary) 0 72%, transparent 72% 100%)",
          }}
        />
        <input
          aria-label={mergedLabels.slider}
          aria-valuemax={latest}
          aria-valuemin={earliest}
          aria-valuenow={value}
          aria-valuetext={valueText}
          className="relative z-10 h-8 w-full cursor-pointer appearance-none bg-transparent"
          max={latest}
          min={earliest}
          onChange={(event) =>
            schedulePreview(Number(event.currentTarget.value))
          }
          onKeyDown={handleKeyDown}
          step={HOUR}
          type="range"
          value={Math.min(Math.max(value, earliest), latest)}
        />
        <TemporalCursorMarker position={markerPosition} />
        {cursor.eventPoints.slice(0, 24).map((point) => (
          <span
            key={point.id}
            aria-hidden="true"
            className="absolute top-1/2 z-0 h-2 w-px -translate-y-1/2 bg-[var(--line)]"
            style={{
              left: `${eventPosition(point, earliest, latest) * 100}%`,
            }}
          />
        ))}
      </div>
      <TemporalLegend
        observedLabel={mergedLabels.observed}
        simulatedLabel={mergedLabels.simulated}
      />
      <Button
        aria-label={mergedLabels.now}
        leading={<Clock aria-hidden="true" size={14} />}
        onClick={() => commitValue(latest)}
        size="sm"
        type="button"
        variant="ghost"
      >
        {mergedLabels.now}
      </Button>
      <span aria-atomic="true" aria-live="polite" className="sr-only">
        {announcement}
      </span>
      <span className="text-muted hidden min-w-[9rem] text-right font-mono text-[11px] md:block">
        {formatTemporalDate(effectiveValidAt, navigator.language)}
      </span>
    </div>
  );
}

function eventPosition(
  point: TemporalEventPoint,
  earliest: number,
  latest: number,
) {
  const timestamp = new Date(point.timestamp).getTime();
  if (!Number.isFinite(timestamp) || latest <= earliest) {
    return 0;
  }
  return Math.min(Math.max((timestamp - earliest) / (latest - earliest), 0), 1);
}

function snapIfNeeded(
  value: string,
  points: TemporalEventPoint[],
  reducedMotion: boolean,
) {
  if (!reducedMotion || points.length === 0) {
    return value;
  }
  const target = new Date(value).getTime();
  return (
    points
      .map((point) => ({
        distance: Math.abs(new Date(point.timestamp).getTime() - target),
        timestamp: point.timestamp,
      }))
      .sort((left, right) => left.distance - right.distance)[0]?.timestamp ??
    value
  );
}
