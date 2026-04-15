import { cn } from "@/lib/utils";

type NarrativeTransitionProps = {
  direction?: "down" | "forward";
  label?: string;
  className?: string;
};

export function NarrativeTransition({
  direction = "down",
  label,
  className,
}: NarrativeTransitionProps) {
  return (
    <div
      className={cn("flex items-center justify-center py-6", className)}
      aria-hidden="true"
    >
      <div className="flex flex-col items-center gap-1">
        {label && (
          <span className="text-muted text-xs font-medium">{label}</span>
        )}
        <span className="text-muted text-xl">
          {direction === "down" ? "\u2193" : "\u2192"}
        </span>
      </div>
    </div>
  );
}
