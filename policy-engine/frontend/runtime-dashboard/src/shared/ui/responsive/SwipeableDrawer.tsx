import { useCallback, useEffect, useRef, useState } from "react";

import { useOptionalI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SwipeableDrawerProps = {
  open: boolean;
  onClose: () => void;
  side?: "left" | "right";
  width?: number;
  title?: string;
  children: React.ReactNode;
  className?: string;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SwipeableDrawer({
  open,
  onClose,
  side = "left",
  width = 280,
  title,
  children,
  className,
}: SwipeableDrawerProps) {
  const { t } = useOptionalI18n();
  const dragStartX = useRef<number | null>(null);
  const [translateX, setTranslateX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    dragStartX.current = e.touches[0].clientX;
    setIsDragging(true);
    setTranslateX(0);
  }, []);

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (dragStartX.current == null) return;
      const dx = e.touches[0].clientX - dragStartX.current;
      if (side === "left" && dx < 0) {
        setTranslateX(dx);
      } else if (side === "right" && dx > 0) {
        setTranslateX(dx);
      }
    },
    [side],
  );

  const handleTouchEnd = useCallback(() => {
    setIsDragging(false);
    if (Math.abs(translateX) > width * 0.4) {
      onClose();
    }
    setTranslateX(0);
    dragStartX.current = null;
  }, [translateX, width, onClose]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  const transform = translateX !== 0 ? `translateX(${translateX}px)` : undefined;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[var(--z-overlay)] bg-black/30"
        onClick={onClose}
        aria-hidden
      />

      {/* Drawer */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title ?? t("common.drawer")}
        className={cn(
          "bg-paper fixed top-0 bottom-0 z-[var(--z-modal)] shadow-lg transition-transform duration-300 ease-out",
          side === "left" ? "left-0" : "right-0",
          className,
        )}
        style={{
          width,
          transform,
          willChange: isDragging ? "transform" : undefined,
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {/* Header */}
        {title && (
          <div className="border-line flex items-center justify-between border-b px-4 py-3">
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
        <div className="overflow-y-auto p-4" style={{ maxHeight: "calc(100% - 56px)" }}>
          {children}
        </div>
      </div>
    </>
  );
}
