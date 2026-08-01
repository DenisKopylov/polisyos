import {
  createInteractionState,
  type InteractionState,
} from "@/shared/lib/domain/statusOwnership";
import { cn } from "@/shared/lib/utils";

export type InsightLevel = InteractionState;

type InsightCalloutProps = {
  level?: InsightLevel;
  title?: string;
  children: React.ReactNode;
  className?: string;
};

export function InsightCallout({
  level = createInteractionState("insight", "candidate_display"),
  title,
  children,
  className,
}: InsightCalloutProps) {
  return (
    <div
      className={cn("border-line bg-panel rounded-2xl border p-4", className)}
      data-interaction-purpose={level.authorityPurpose}
      role="note"
    >
      <div className="flex items-start gap-3">
        <span className="text-muted mt-0.5 text-lg" aria-hidden>
          {"\u2022"}
        </span>
        <div className="min-w-0 flex-1">
          <span className="text-muted text-xs">{level.label}</span>
          {title && (
            <p
              className="text-sm font-semibold"
              data-authored-exempt="true"
              data-authored-exempt-reason="Insight callout title is structural callout chrome; callout children carry authored prose where needed."
            >
              {title}
            </p>
          )}
          <div className="mt-0.5 text-sm">{children}</div>
        </div>
      </div>
    </div>
  );
}
