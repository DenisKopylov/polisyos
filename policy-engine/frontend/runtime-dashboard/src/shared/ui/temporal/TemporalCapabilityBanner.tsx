import { cn } from "@/lib/utils";

type TemporalCapabilityBannerProps = {
  title?: string;
  body?: string;
  tone?: "gap" | "unsupported";
  className?: string;
};

const DEFAULT_COPY = {
  body: "This surface cannot reproduce the selected temporal scope yet.",
  title: "Temporal gap",
};

export function TemporalCapabilityBanner({
  body = DEFAULT_COPY.body,
  className,
  title = DEFAULT_COPY.title,
  tone = "gap",
}: TemporalCapabilityBannerProps) {
  return (
    <div
      className={cn(
        "border-line bg-panel text-text rounded-[var(--radius-card)] border px-3 py-2 text-xs",
        tone === "unsupported" && "border-warning/40 bg-warning/10",
        className,
      )}
      role="status"
    >
      <strong className="font-extrabold">{title}</strong>
      <span className="text-muted ml-2">{body}</span>
    </div>
  );
}
