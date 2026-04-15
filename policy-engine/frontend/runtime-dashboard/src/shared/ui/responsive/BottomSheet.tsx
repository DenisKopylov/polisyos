import { useCallback, useEffect, useRef, useState } from "react";

import { useOptionalI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BottomSheetProps = {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  snapPoints?: number[];
  className?: string;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BottomSheet({
  open,
  onClose,
  title,
  children,
  snapPoints = [0.4, 0.75, 1],
  className,
}: BottomSheetProps) {
  const { t } = useOptionalI18n();
  const [snapIndex, setSnapIndex] = useState(0);
  const sheetRef = useRef<HTMLDivElement>(null);
  const dragStartY = useRef<number | null>(null);
  const currentSnapHeight = snapPoints[snapIndex] ?? 0.4;

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    dragStartY.current = e.touches[0].clientY;
  }, []);

  const handleTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      if (dragStartY.current == null) return;
      const deltaY = e.changedTouches[0].clientY - dragStartY.current;
      dragStartY.current = null;

      if (deltaY > 80) {
        // Swipe down
        if (snapIndex > 0) {
          setSnapIndex(snapIndex - 1);
        } else {
          onClose();
        }
      } else if (deltaY < -80) {
        // Swipe up
        if (snapIndex < snapPoints.length - 1) {
          setSnapIndex(snapIndex + 1);
        }
      }
    },
    [snapIndex, snapPoints.length, onClose],
  );

  useEffect(() => {
    if (!open) {
      setSnapIndex(0);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[var(--z-overlay)] bg-black/30"
        onClick={onClose}
        aria-hidden
      />

      {/* Sheet */}
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-label={title ?? t("common.bottomSheet")}
        className={cn(
          "bg-paper fixed inset-x-0 bottom-0 z-[var(--z-modal)] rounded-t-2xl shadow-lg transition-[height] duration-300 ease-out",
          className,
        )}
        style={{ height: `${currentSnapHeight * 100}vh` }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {/* Drag handle */}
        <div className="flex justify-center py-3">
          <div className="bg-line h-1 w-10 rounded-full" />
        </div>

        {/* Header */}
        {title && (
          <div className="flex items-center justify-between px-4 pb-2">
            <h3 className="text-sm font-semibold">{title}</h3>
            <button
              type="button"
              onClick={onClose}
              className="text-muted hover:text-foreground focus-visible:outline-accent/45 rounded-md text-lg focus-visible:outline-2 focus-visible:outline-offset-2"
              aria-label={t("common.close")}
            >
              ×
            </button>
          </div>
        )}

        {/* Content */}
        <div className="overflow-y-auto px-4 pb-8" style={{ maxHeight: "calc(100% - 64px)" }}>
          {children}
        </div>
      </div>
    </>
  );
}
