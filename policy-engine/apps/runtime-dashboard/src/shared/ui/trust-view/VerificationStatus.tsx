import { AlertTriangle, CheckCircle2, CircleHelp, Clock3 } from "lucide-react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import {
  trustPresentationFromMetadata,
  type VerificationMetadata,
} from "./trust-glyphs";

type VerificationStatusProps = {
  metadata?: VerificationMetadata | null;
  className?: string;
  showLabel?: boolean;
};

export function VerificationStatus({
  metadata,
  className,
  showLabel = true,
}: VerificationStatusProps) {
  const { t } = useI18n();
  const presentation = trustPresentationFromMetadata(metadata);
  const label =
    presentation.tone === "unknown"
      ? t("common.unknown")
      : t(`shared.ui.trustView.status.${presentation.tone}`);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
        toneClassName(presentation.tone),
        className,
      )}
      aria-label={label}
      data-verification-presentation={presentation.tone}
      data-verification-source={
        presentation.ownerContractPresent
          ? "generated-owner"
          : "absent-or-incomplete"
      }
    >
      <StatusIcon tone={presentation.tone} />
      <span aria-hidden={!showLabel}>
        {showLabel ? label : trustGlyph(presentation.tone)}
      </span>
    </span>
  );
}

function toneClassName(tone: string) {
  if (tone === "verified") {
    return "border-[color-mix(in_srgb,var(--color-status-approved)_34%,transparent)] bg-[color-mix(in_srgb,var(--color-status-approved)_10%,transparent)] text-[var(--color-status-approved)]";
  }
  if (tone === "pending") {
    return "border-[color-mix(in_srgb,var(--color-status-pending)_34%,transparent)] bg-[color-mix(in_srgb,var(--color-status-pending)_10%,transparent)] text-[var(--color-status-pending)]";
  }
  if (tone === "disputed") {
    return "border-[color-mix(in_srgb,var(--color-status-rejected)_34%,transparent)] bg-[color-mix(in_srgb,var(--color-status-rejected)_10%,transparent)] text-[var(--color-status-rejected)]";
  }
  return tone === "stale"
    ? "border-border bg-muted/60 text-muted-foreground"
    : "border-border bg-muted/40 text-muted-foreground";
}

function trustGlyph(tone: string) {
  if (tone === "verified") return "✓";
  if (tone === "pending") return "◌";
  if (tone === "disputed") return "!";
  if (tone === "stale") return "~";
  return "?";
}

function StatusIcon({ tone }: { tone: string }) {
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
