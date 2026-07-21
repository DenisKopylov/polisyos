import { useI18n } from "@/shared/i18n/LocaleProvider";

import { VerificationStatus } from "./VerificationStatus";
import type { VerificationMetadata } from "./trust-glyphs";

type TrustViewBadgeProps = {
  metadata?: VerificationMetadata | null;
};

export function TrustViewBadge({ metadata }: TrustViewBadgeProps) {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-muted-foreground text-[11px] font-semibold">
        {t("shared.ui.trustView.label")}
      </span>
      <VerificationStatus metadata={metadata} />
    </span>
  );
}
