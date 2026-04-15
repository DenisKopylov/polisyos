import { AnimatePresence, motion } from "motion/react";
import { useMemo, type RefObject } from "react";

import { useCollaborationStore } from "../state/useCollaborationStore";
import type { CollaborationCursor } from "../types";

type CollaborativeCursorsProps = {
  /** Container ref to compute relative positions. */
  containerRef?: RefObject<HTMLElement | null>;
  className?: string;
};

type CursorOverlayProps = {
  cursor: CollaborationCursor;
};

function CursorOverlay({ cursor }: CursorOverlayProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.5 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className="pointer-events-none absolute"
      style={{
        left: `${cursor.x * 100}%`,
        top: `${cursor.y * 100}%`,
        transform: "translate(-2px, -2px)",
      }}
    >
      {/* Cursor arrow (SVG) */}
      <svg
        width="16"
        height="20"
        viewBox="0 0 16 20"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="drop-shadow-sm"
      >
        <path
          d="M1 1L1 15L5.5 11L10.5 18L13 16.5L8 9.5L14 8.5L1 1Z"
          fill={cursor.accentColor}
          stroke="white"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </svg>

      {/* Name label */}
      <motion.div
        initial={{ opacity: 0, x: 4 }}
        animate={{ opacity: 1, x: 0 }}
        className="ml-3 mt-0.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold text-white shadow-md"
        style={{ backgroundColor: cursor.accentColor }}
      >
        {cursor.displayName}
      </motion.div>
    </motion.div>
  );
}

/**
 * Renders other participants' cursors as an overlay.
 * Mount this as a child of the collaboration surface container
 * (must have `position: relative` and `overflow: hidden`).
 */
export function CollaborativeCursors({
  className,
}: CollaborativeCursorsProps) {
  const cursors = useCollaborationStore((s) => s.cursors);

  const visibleCursors = useMemo(
    () =>
      cursors.filter(
        (c) => Number.isFinite(c.x) && Number.isFinite(c.y),
      ),
    [cursors],
  );

  if (visibleCursors.length === 0) return null;

  return (
    <div
      className={`pointer-events-none absolute inset-0 z-[var(--z-overlay)] overflow-hidden ${className ?? ""}`}
    >
      <AnimatePresence>
        {visibleCursors.map((cursor) => (
          <CursorOverlay key={cursor.participantId} cursor={cursor} />
        ))}
      </AnimatePresence>
    </div>
  );
}
