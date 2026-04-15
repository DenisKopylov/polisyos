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

const LAYOUTS: { value: LayoutAlgorithm; label: string }[] = [
  { value: "hierarchical", label: "Hierarchical" },
  { value: "sugiyama", label: "Sugiyama" },
  { value: "force", label: "Force" },
];

const OVERLAYS: { value: OverlayMode; label: string }[] = [
  { value: "none", label: "None" },
  { value: "identification", label: "Identification" },
  { value: "transport", label: "Transport" },
  { value: "adjustment_set", label: "Adjustment set" },
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
  return (
    <div
      className={cn(
        "bg-surface/90 border-line flex flex-wrap items-center gap-3 rounded-xl border px-3 py-2 backdrop-blur-sm",
        className,
      )}
      role="toolbar"
      aria-label="Graph controls"
    >
      {/* Layout selector */}
      <div className="flex items-center gap-1.5">
        <span className="text-muted text-xs font-medium">Layout</span>
        <div className="border-line flex rounded-lg border">
          {LAYOUTS.map((l) => (
            <button
              key={l.value}
              type="button"
              className={cn(
                "px-2 py-1 text-xs font-medium transition-colors",
                layout === l.value
                  ? "bg-[var(--chart-primary)] text-white"
                  : "text-muted hover:text-inherit",
                l.value === "hierarchical" && "rounded-l-lg",
                l.value === "force" && "rounded-r-lg",
              )}
              onClick={() => onLayoutChange(l.value)}
              aria-pressed={layout === l.value}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Divider */}
      <div className="bg-line h-5 w-px" />

      {/* Overlay selector */}
      <div className="flex items-center gap-1.5">
        <span className="text-muted text-xs font-medium">Overlay</span>
        <select
          value={overlay}
          onChange={(e) => onOverlayChange(e.target.value as OverlayMode)}
          className="bg-surface border-line rounded-lg border px-2 py-1 text-xs"
        >
          {OVERLAYS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
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
          className="text-muted hover:text-inherit rounded-lg p-1 text-sm"
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          type="button"
          onClick={onZoomOut}
          className="text-muted hover:text-inherit rounded-lg p-1 text-sm"
          aria-label="Zoom out"
        >
          −
        </button>
        <button
          type="button"
          onClick={onFitView}
          className="text-muted hover:text-inherit rounded-lg px-2 py-1 text-xs font-medium"
          aria-label="Fit to view"
        >
          Fit
        </button>
      </div>
    </div>
  );
}
