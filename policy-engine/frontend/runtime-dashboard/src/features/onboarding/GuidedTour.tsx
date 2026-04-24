import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/LocaleProvider";
import { Button } from "@/shared/ui/primitives";
import { fadeInScale, reducedMotion } from "@/shared/ui/motion";
import {
  trackOnboardingCompleted,
  trackOnboardingDismissed,
  trackOnboardingStepCompleted,
} from "@/shared/telemetry/extendedEvents";

import type { TourDefinition, TourStep } from "./types";

type GuidedTourProps = {
  tour: TourDefinition;
  onComplete: () => void;
  onDismiss: () => void;
};

type TargetRect = {
  bottom: number;
  height: number;
  left: number;
  right: number;
  top: number;
  width: number;
};

const PADDING = 8;
const TOOLTIP_GAP = 12;

function getTargetRect(selector: string): TargetRect | null {
  const el = document.querySelector(selector);
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  return {
    bottom: rect.bottom,
    height: rect.height,
    left: rect.left,
    right: rect.right,
    top: rect.top,
    width: rect.width,
  };
}

function getTooltipPosition(
  rect: TargetRect,
  placement: TourStep["placement"],
): { left: number; top: number } {
  switch (placement) {
    case "top":
      return {
        left: rect.left + rect.width / 2,
        top: rect.top - TOOLTIP_GAP,
      };
    case "bottom":
      return {
        left: rect.left + rect.width / 2,
        top: rect.bottom + TOOLTIP_GAP,
      };
    case "left":
      return {
        left: rect.left - TOOLTIP_GAP,
        top: rect.top + rect.height / 2,
      };
    case "right":
    default:
      return {
        left: rect.right + TOOLTIP_GAP,
        top: rect.top + rect.height / 2,
      };
  }
}

/**
 * Guided onboarding tour overlay.
 *
 * Renders a spotlight cutout on the target element with a tooltip.
 * Supports keyboard navigation (Escape to dismiss, arrows to navigate).
 */
export function GuidedTour({ tour, onComplete, onDismiss }: GuidedTourProps) {
  const { t } = useI18n();
  const prefersReducedMotion = useReducedMotion();
  const [stepIndex, setStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);

  const step = tour.steps[stepIndex];
  const isFirst = stepIndex === 0;
  const isLast = stepIndex === tour.steps.length - 1;

  // Measure target element
  useEffect(() => {
    if (!step) return;

    let cancelled = false;
    let rafId = 0;

    const measure = () => {
      const rect = getTargetRect(step.target);
      setTargetRect(rect);
      return rect;
    };

    const skipMissingStep = () => {
      if (cancelled) {
        return;
      }
      if (stepIndex < tour.steps.length - 1) {
        setTargetRect(null);
        setStepIndex((current) => current + 1);
        return;
      }
      trackOnboardingDismissed(stepIndex, "missing_target");
      onDismiss();
    };

    const mountTracking = () => {
      if (cancelled) {
        return;
      }
      step.onEnter?.();

      // Re-measure on resize/scroll
      window.addEventListener("resize", measure);
      window.addEventListener("scroll", measure, true);

      const el = document.querySelector(step.target);
      if (el) {
        observerRef.current = new ResizeObserver(() => {
          void measure();
        });
        observerRef.current.observe(el);
      }
    };

    const initialRect = measure();
    if (initialRect) {
      mountTracking();
    } else {
      rafId = window.requestAnimationFrame(() => {
        const retriedRect = measure();
        if (retriedRect) {
          mountTracking();
          return;
        }
        skipMissingStep();
      });
    }

    return () => {
      cancelled = true;
      window.cancelAnimationFrame(rafId);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
      observerRef.current?.disconnect();
      observerRef.current = null;
    };
  }, [onDismiss, step, stepIndex, tour.steps.length]);

  const handleNext = useCallback(() => {
    if (!step) return;
    trackOnboardingStepCompleted(step.id, stepIndex);

    if (isLast) {
      trackOnboardingCompleted(tour.steps.length);
      onComplete();
    } else {
      setStepIndex((i) => i + 1);
    }
  }, [isLast, onComplete, step, stepIndex, tour.steps.length]);

  const handlePrev = useCallback(() => {
    setStepIndex((i) => Math.max(0, i - 1));
  }, []);

  const handleDismiss = useCallback(() => {
    trackOnboardingDismissed(stepIndex, "user");
    onDismiss();
  }, [onDismiss, stepIndex]);

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleDismiss();
      if (e.key === "ArrowRight") handleNext();
      if (e.key === "ArrowLeft") handlePrev();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleDismiss, handleNext, handlePrev]);

  const tooltipVariants = useMemo(
    () => (prefersReducedMotion ? reducedMotion(fadeInScale) : fadeInScale),
    [prefersReducedMotion],
  );

  if (!step || !targetRect) return null;

  const tooltipPos = getTooltipPosition(targetRect, step.placement);

  return (
    <div
      className="fixed inset-0 z-[var(--z-command)]"
      role="dialog"
      aria-modal="true"
      aria-label={t("onboarding.tourLabel")}
    >
      {/* Backdrop with spotlight cutout */}
      <svg className="absolute inset-0 h-full w-full">
        <defs>
          <mask id="tour-spotlight">
            <rect width="100%" height="100%" fill="white" />
            <rect
              x={targetRect.left - PADDING}
              y={targetRect.top - PADDING}
              width={targetRect.width + PADDING * 2}
              height={targetRect.height + PADDING * 2}
              rx="12"
              fill="black"
            />
          </mask>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="rgba(0,0,0,0.5)"
          mask="url(#tour-spotlight)"
        />
        {/* Spotlight border */}
        <rect
          x={targetRect.left - PADDING}
          y={targetRect.top - PADDING}
          width={targetRect.width + PADDING * 2}
          height={targetRect.height + PADDING * 2}
          rx="12"
          fill="none"
          stroke="var(--teal)"
          strokeWidth="2"
          strokeDasharray="4 4"
        />
      </svg>

      {/* Tooltip */}
      <AnimatePresence mode="wait">
        <motion.div
          key={step.id}
          variants={tooltipVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className={cn(
            "bg-popover text-popover-foreground border-border absolute z-10 w-72 rounded-2xl border p-4 shadow-xl",
            step.placement === "top" && "-translate-x-1/2 -translate-y-full",
            step.placement === "bottom" && "-translate-x-1/2",
            step.placement === "left" && "-translate-x-full -translate-y-1/2",
            step.placement === "right" && "-translate-y-1/2",
          )}
          style={{ left: tooltipPos.left, top: tooltipPos.top }}
        >
          {/* Close button */}
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground absolute top-2 right-2 rounded-md p-1"
            onClick={handleDismiss}
            aria-label={t("common.close")}
          >
            <X className="h-4 w-4" />
          </button>

          {/* Step counter */}
          <p className="text-muted-foreground mb-1 text-[11px] font-medium">
            {stepIndex + 1} / {tour.steps.length}
          </p>

          <h3 className="text-sm font-semibold">{t(step.title)}</h3>
          <p className="text-muted-foreground mt-1 text-sm">
            {t(step.description)}
          </p>

          {/* Navigation */}
          <div className="mt-3 flex items-center justify-between">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handlePrev}
              disabled={isFirst}
            >
              <ChevronLeft className="mr-1 h-3.5 w-3.5" />
              {t("onboarding.prev")}
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={handleNext}
            >
              {isLast ? t("onboarding.finish") : t("onboarding.next")}
              {!isLast && <ChevronRight className="ml-1 h-3.5 w-3.5" />}
            </Button>
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
