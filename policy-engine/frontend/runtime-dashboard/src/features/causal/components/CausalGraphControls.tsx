import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

import type { LayoutAlgorithm, OverlayMode } from "../types";

type CausalGraphControlsProps = {
  layout: LayoutAlgorithm;
  overlay: OverlayMode;
  onLayoutChange: (layout: LayoutAlgorithm) => void;
  onOverlayChange: (overlay: OverlayMode) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitView: () => void;
  className?: string;
};

const LAYOUTS: LayoutAlgorithm[] = ["hierarchical", "sugiyama", "force"];
const OVERLAYS: OverlayMode[] = [
  "none",
  "identification",
  "transport",
  "adjustment_set",
];

export function CausalGraphControls({
  layout,
  overlay,
  onLayoutChange,
  onOverlayChange,
  onZoomIn,
  onZoomOut,
  onFitView,
  className,
}: CausalGraphControlsProps) {
  const { t } = useI18n();

  const layoutLabels: Record<LayoutAlgorithm, string> = {
    hierarchical: t("causal.layout.hierarchical"),
    sugiyama: t("causal.layout.sugiyama"),
    force: t("causal.layout.force"),
  };
  const overlayLabels: Record<OverlayMode, string> = {
    none: t("causal.overlay.none"),
    identification: t("causal.overlay.identification"),
    transport: t("causal.overlay.transport"),
    adjustment_set: t("causal.overlay.adjustmentSet"),
  };

  return (
    <div
      className={cn(
        "bg-surface/90 border-line flex flex-wrap items-center gap-3 rounded-xl border px-3 py-2 backdrop-blur-sm",
        className,
      )}
      role="toolbar"
      aria-label={t("causal.controls.graphControls")}
    >
      {/* Layout selector */}
      <div className="flex items-center gap-1.5">
        <span className="text-muted text-xs font-medium">
          {t("causal.controls.layout")}
        </span>
        <div className="border-line flex rounded-lg border">
          {LAYOUTS.map((layoutValue) => (
            <button
              key={layoutValue}
              type="button"
              className={cn(
                "px-2 py-1 text-xs font-medium transition-colors",
                layout === layoutValue
                  ? "bg-[var(--chart-primary)] text-white"
                  : "text-muted hover:text-inherit",
                layoutValue === "hierarchical" && "rounded-l-lg",
                layoutValue === "force" && "rounded-r-lg",
              )}
              onClick={() => onLayoutChange(layoutValue)}
              aria-pressed={layout === layoutValue}
            >
              {layoutLabels[layoutValue]}
            </button>
          ))}
        </div>
      </div>

      {/* Divider */}
      <div className="bg-line h-5 w-px" />

      {/* Overlay selector */}
      <div className="flex items-center gap-1.5">
        <span className="text-muted text-xs font-medium">
          {t("causal.controls.overlay")}
        </span>
        <select
          value={overlay}
          onChange={(e) => onOverlayChange(e.target.value as OverlayMode)}
          className="bg-surface border-line rounded-lg border px-2 py-1 text-xs"
        >
          {OVERLAYS.map((overlayValue) => (
            <option key={overlayValue} value={overlayValue}>
              {overlayLabels[overlayValue]}
            </option>
          ))}
        </select>
      </div>

      {/* Divider */}
      <div className="bg-line h-5 w-px" />

      {/* Zoom controls */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onZoomIn}
          className="text-muted rounded-lg p-1 text-sm hover:text-inherit"
          aria-label={t("causal.controls.zoomIn")}
        >
          +
        </button>
        <button
          type="button"
          onClick={onZoomOut}
          className="text-muted rounded-lg p-1 text-sm hover:text-inherit"
          aria-label={t("causal.controls.zoomOut")}
        >
          -
        </button>
        <button
          type="button"
          onClick={onFitView}
          className="text-muted rounded-lg px-2 py-1 text-xs font-medium hover:text-inherit"
          aria-label={t("causal.controls.fitToView")}
        >
          {t("causal.controls.fit")}
        </button>
      </div>
    </div>
  );
}
