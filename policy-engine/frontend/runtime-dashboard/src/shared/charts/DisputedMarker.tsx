import { cn } from "@/shared/lib/utils";
import { Glyph } from "@/shared/brand/Glyph";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/ui/Tooltip";

import type { DisputeSummary } from "./types";
import { uncertaintyTokens } from "./uncertainty-tokens";

type DisputedMarkerProps = {
  disputes?: DisputeSummary[];
  label?: string;
  className?: string;
};

function disputeSummary(disputes: DisputeSummary[]) {
  if (disputes.length === 0) {
    return "Disputed. Attribution details unavailable.";
  }
  return disputes
    .map((dispute) => {
      const who = dispute.who.trim() || "Unknown reviewer";
      const asOf = dispute.asOf ? ` on ${dispute.asOf}` : "";
      const source = dispute.source ? ` via ${dispute.source}` : "";
      return `${who}${asOf}${source}: ${dispute.why}`;
    })
    .join(" ");
}

export function DisputedMarker({
  disputes = [],
  label = "Disputed",
  className,
}: DisputedMarkerProps) {
  const summary = disputeSummary(disputes);

  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold tracking-[0.14em] uppercase",
              className,
            )}
            style={{
              borderColor: uncertaintyTokens.disputed,
              color: uncertaintyTokens.disputed,
            }}
            aria-label={`${label}. ${summary}`}
          >
            <Glyph
              name="counterfactual"
              size={12}
              intent="blocked"
              title={label}
            />
            <span>{label}</span>
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-72 space-y-1">
          <p
            className="font-semibold"
            style={{ color: uncertaintyTokens.disputed }}
          >
            {label}
          </p>
          <p className="leading-5">{summary}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
