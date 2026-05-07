import { ShieldCheck } from "lucide-react";

import { useMaybeTrustView } from "@/app/providers/useTrustView";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

type TrustViewToggleProps = {
  className?: string;
};

export function TrustViewToggle({ className }: TrustViewToggleProps) {
  const trustView = useMaybeTrustView();
  const { t } = useI18n();
  if (!trustView) {
    return null;
  }
  const { cycleMode, mode } = trustView;
  return (
    <button
      type="button"
      className={cn("trust-view-toggle", className)}
      aria-label={t("shared.ui.trustView.toggleAria", {
        mode: t(`shared.ui.trustView.mode.${mode}`),
      })}
      aria-pressed={mode !== "off"}
      data-mode={mode}
      onClick={cycleMode}
    >
      <ShieldCheck className="size-4" aria-hidden="true" />
      <span>{t(`shared.ui.trustView.mode.${mode}`)}</span>
    </button>
  );
}
