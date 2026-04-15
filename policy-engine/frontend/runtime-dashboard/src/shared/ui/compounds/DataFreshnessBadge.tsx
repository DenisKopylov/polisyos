import { useI18n } from "@/i18n/LocaleProvider";
import { formatDate, formatRelativeTime } from "@/lib/utils";
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

  if (!generatedAt) {
    return <Badge kind="warn">{t("common.freshness.missing")}</Badge>;
  }

  const date = new Date(generatedAt);
  if (Number.isNaN(date.getTime())) {
    return <Badge kind="warn">{t("common.freshness.invalid")}</Badge>;
  }

  const ageMs = Date.now() - date.getTime();
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
