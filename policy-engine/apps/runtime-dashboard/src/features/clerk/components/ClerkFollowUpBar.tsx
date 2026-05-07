import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";

type FollowUpAction = {
  label: string;
  /** The question or command to execute. */
  value: string;
  icon?: string;
};

type ClerkFollowUpBarProps = {
  actions: FollowUpAction[];
  onAction: (value: string) => void;
  className?: string;
};

const DEFAULT_FOLLOW_UPS: FollowUpAction[] = [
  {
    label: "Compare with previous",
    value: "Compare this analysis with the previous run",
    icon: "\u21C4",
  },
  {
    label: "Explain methodology",
    value: "Explain the methodology used in this analysis",
    icon: "\u2139",
  },
  {
    label: "Show data sources",
    value: "Show all data sources used",
    icon: "\uD83D\uDCCE",
  },
  {
    label: "Export as report",
    value: "Export this conversation as a report",
    icon: "\uD83D\uDCC4",
  },
];

export function ClerkFollowUpBar({
  actions,
  onAction,
  className,
}: ClerkFollowUpBarProps) {
  const { t } = useI18n();
  const items = actions.length > 0 ? actions : DEFAULT_FOLLOW_UPS;

  return (
    <div
      className={cn(
        "flex items-center gap-2 overflow-x-auto border-t border-[var(--line)] bg-[var(--panel)] px-4 py-2",
        className,
      )}
      role="toolbar"
      aria-label={t("clerk.followUpActions")}
    >
      <span className="shrink-0 text-xs font-semibold text-[var(--slate)]">
        {t("clerk.followUp")}:
      </span>
      {items.map((action, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onAction(action.value)}
          className="flex shrink-0 items-center gap-1.5 rounded-[var(--radius-pill)] border border-[var(--line)] bg-[var(--surface)] px-3 py-1 text-xs font-medium text-[var(--ink)] transition-colors hover:border-[var(--teal)] hover:bg-[var(--teal-soft)] focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:outline-none"
        >
          {action.icon && <span aria-hidden="true">{action.icon}</span>}
          {action.label}
        </button>
      ))}
    </div>
  );
}

export { DEFAULT_FOLLOW_UPS };
export type { FollowUpAction };
