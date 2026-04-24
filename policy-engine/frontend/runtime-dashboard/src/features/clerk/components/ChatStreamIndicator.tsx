import { useI18n } from "@/i18n/LocaleProvider";

export function ChatStreamIndicator() {
  const { t } = useI18n();

  return (
    <div
      className="flex items-center gap-1.5 py-1"
      aria-label={t("clerk.processing")}
    >
      <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--teal)]" />
      <span
        className="h-2 w-2 animate-pulse rounded-full bg-[var(--teal)]"
        style={{ animationDelay: "150ms" }}
      />
      <span
        className="h-2 w-2 animate-pulse rounded-full bg-[var(--teal)]"
        style={{ animationDelay: "300ms" }}
      />
    </div>
  );
}
