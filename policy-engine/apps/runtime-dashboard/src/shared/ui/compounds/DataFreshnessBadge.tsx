import { useState } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatDate, formatRelativeTime } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/primitives";

type DataFreshnessBadgeProps = {
  generatedAt?: string | null;
  staleAfterMs?: number;
};

export function DataFreshnessBadge({
  generatedAt,
  staleAfterMs = 5 * 60_000,
}: DataFreshnessBadgeProps) {
  const { locale, t } = useI18n();
  const [renderedAtMs] = useState(() => Date.now());

  if (!generatedAt) {
    return <Badge kind="warn">{t("common.freshness.missing")}</Badge>;
  }

  const date = new Date(generatedAt);
  if (Number.isNaN(date.getTime())) {
    return <Badge kind="warn">{t("common.freshness.invalid")}</Badge>;
  }

  const ageMs = renderedAtMs - date.getTime();
  return (
    <Badge
      kind={ageMs > staleAfterMs ? "warn" : "ok"}
      className="tracking-normal normal-case"
      title={formatDate(date, locale)}
    >
      {t("common.freshness.updated", {
        value: formatRelativeTime(date, locale),
      })}
    </Badge>
  );
}
