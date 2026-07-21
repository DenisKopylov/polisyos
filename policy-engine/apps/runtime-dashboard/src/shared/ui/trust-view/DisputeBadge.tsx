import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import type { VerificationMetadata } from "./trust-glyphs";

type DisputeBadgeProps = {
  status: VerificationMetadata["dispute_status"];
  className?: string;
};

export function DisputeBadge({ status, className }: DisputeBadgeProps) {
  const { t } = useI18n();
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold",
        status === "none" || status === "resolved"
          ? "border-border bg-muted/30 text-muted-foreground"
          : "border-[color-mix(in_srgb,var(--color-status-rejected)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-status-rejected)_8%,transparent)] text-[var(--color-status-rejected)]",
        className,
      )}
    >
      {t(`shared.ui.trustView.dispute.${status}`)}
    </span>
  );
}
