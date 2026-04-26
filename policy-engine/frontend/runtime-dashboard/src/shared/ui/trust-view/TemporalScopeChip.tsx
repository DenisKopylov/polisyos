import { useI18n } from "@/i18n/LocaleProvider";

import type { TemporalRef } from "@/shared/ui/quantity";

type TemporalScopeChipProps = {
  scope?: TemporalRef | null;
};

export function TemporalScopeChip({ scope }: TemporalScopeChipProps) {
  const { t } = useI18n();
  const validAt = scope?.valid_at ?? t("shared.ui.trustView.latest");
  const txAt = scope?.tx_at ?? t("shared.ui.trustView.latest");
  return (
    <span className="border-border bg-muted/30 inline-flex max-w-full items-center rounded-full border px-2 py-0.5 font-mono text-[11px]">
      {t("shared.ui.trustView.temporalScope", { txAt, validAt })}
    </span>
  );
}
