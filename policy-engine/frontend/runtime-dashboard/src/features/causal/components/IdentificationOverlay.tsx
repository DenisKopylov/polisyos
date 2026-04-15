import { cn } from "@/lib/utils";

import type { CausalEdgeData } from "../types";

type IdentificationOverlayProps = {
  edges: CausalEdgeData[];
  className?: string;
};

export function IdentificationOverlay({
  edges,
  className,
}: IdentificationOverlayProps) {
  const identified = edges.filter((e) => e.status === "identified").length;
  const unidentified = edges.filter((e) => e.status === "unidentified").length;
  const boundsOnly = edges.filter((e) => e.status === "bounds_only").length;

  return (
    <div
      className={cn(
        "bg-surface/90 border-line rounded-xl border p-3 text-xs backdrop-blur-sm",
        className,
      )}
    >
      <p className="mb-2 font-semibold">Identification Status</p>
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-0.5 w-5"
            style={{ background: "var(--chart-primary)" }}
          />
          <span>
            Identified{" "}
            <span className="font-bold text-[var(--chart-primary)]">
              {identified}
            </span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-0.5 w-5"
            style={{
              background: "var(--chart-alert)",
              backgroundImage:
                "repeating-linear-gradient(90deg, var(--chart-alert) 0 4px, transparent 4px 8px)",
            }}
          />
          <span>
            Unidentified{" "}
            <span className="font-bold text-[var(--chart-alert)]">
              {unidentified}
            </span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-0.5 w-5"
            style={{
              background: "var(--color-confidence-medium)",
              backgroundImage:
                "repeating-linear-gradient(90deg, var(--color-confidence-medium) 0 2px, transparent 2px 5px)",
            }}
          />
          <span>
            Bounds only{" "}
            <span className="font-bold text-[var(--color-confidence-medium)]">
              {boundsOnly}
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}
