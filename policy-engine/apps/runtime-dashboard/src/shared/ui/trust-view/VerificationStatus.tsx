import { AlertTriangle, CheckCircle2, CircleHelp, Clock3 } from "lucide-react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import {
  isIssuedTrustPresentation,
  presentTrustPresentation,
  type TrustPresentation,
} from "./trust-glyphs";

type VerificationStatusProps = {
  presentation: TrustPresentation;
  className?: string;
  showLabel?: boolean;
};

export function VerificationStatus({
  presentation,
  className,
  showLabel = true,
}: VerificationStatusProps) {
  const { t } = useI18n();
  const { status } = presentTrustPresentation(presentation);
  const label =
    status === "unknown" || status === "unrecognized"
      ? t("common.unknown")
      : t(`shared.ui.trustView.status.${status}`);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
        toneClassName(status),
        className,
      )}
      aria-label={label}
      data-verification-presentation={status}
      data-verification-source={
        isIssuedTrustPresentation(presentation) ? "issued" : "unissued"
      }
    >
      <StatusIcon presentation={presentation} />
      <span aria-hidden={!showLabel}>
        {showLabel ? label : trustGlyph(status)}
      </span>
    </span>
  );
}

function toneClassName(
  tone: ReturnType<typeof presentTrustPresentation>["status"],
) {
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

function trustGlyph(tone: ReturnType<typeof presentTrustPresentation>["status"]) {
  if (tone === "verified") return "✓";
  if (tone === "pending") return "◌";
  if (tone === "disputed") return "!";
  if (tone === "stale") return "~";
  return "?";
}

function StatusIcon({ presentation }: { presentation: TrustPresentation }) {
  const { status: tone } = presentTrustPresentation(presentation);
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
