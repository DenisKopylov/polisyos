import { AlertTriangle, CheckCircle2, CircleHelp, Clock3 } from "lucide-react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

import { trustGlyph, type TrustGlyphTone } from "./trust-glyphs";

type VerificationStatusProps = {
  tone: TrustGlyphTone;
  className?: string;
  showLabel?: boolean;
};

const TONE_CLASS: Record<TrustGlyphTone, string> = {
  verified:
    "border-[color-mix(in_srgb,var(--color-status-approved)_34%,transparent)] bg-[color-mix(in_srgb,var(--color-status-approved)_10%,transparent)] text-[var(--color-status-approved)]",
  pending:
    "border-[color-mix(in_srgb,var(--color-status-pending)_34%,transparent)] bg-[color-mix(in_srgb,var(--color-status-pending)_10%,transparent)] text-[var(--color-status-pending)]",
  disputed:
    "border-[color-mix(in_srgb,var(--color-status-rejected)_34%,transparent)] bg-[color-mix(in_srgb,var(--color-status-rejected)_10%,transparent)] text-[var(--color-status-rejected)]",
  stale: "border-border bg-muted/60 text-muted-foreground",
  untraced: "border-border bg-muted/40 text-muted-foreground",
};

export function VerificationStatus({
  tone,
  className,
  showLabel = true,
}: VerificationStatusProps) {
  const { t } = useI18n();
  const label = t(`shared.ui.trustView.status.${tone}`);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
        TONE_CLASS[tone],
        className,
      )}
      aria-label={label}
    >
      <StatusIcon tone={tone} />
      <span aria-hidden={!showLabel}>
        {showLabel ? label : trustGlyph(tone)}
      </span>
    </span>
  );
}

function StatusIcon({ tone }: { tone: TrustGlyphTone }) {
  const className = "size-3.5";
  if (tone === "verified") {
    return <CheckCircle2 className={className} aria-hidden="true" />;
  }
  if (tone === "pending") {
    return <Clock3 className={className} aria-hidden="true" />;
  }
  if (tone === "disputed") {
    return <AlertTriangle className={className} aria-hidden="true" />;
  }
  return <CircleHelp className={className} aria-hidden="true" />;
}
