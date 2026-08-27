import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import {
  presentTrustPresentation,
  type TrustPresentation,
} from "./trust-glyphs";

type DisputeBadgeProps = {
  presentation: TrustPresentation;
  className?: string;
};

export function DisputeBadge({ presentation, className }: DisputeBadgeProps) {
  const { t } = useI18n();
  const { dispute } = presentTrustPresentation(presentation);
  const label =
    dispute === "unrecognized"
      ? t("common.unknown")
      : t(`shared.ui.trustView.dispute.${dispute}`);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold",
        dispute === "none" || dispute === "resolved"
          ? "border-border bg-muted/30 text-muted-foreground"
          : "border-[color-mix(in_srgb,var(--color-status-rejected)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-status-rejected)_8%,transparent)] text-[var(--color-status-rejected)]",
        className,
      )}
    >
      {label}
    </span>
  );
}
