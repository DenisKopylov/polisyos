import { useI18n } from "@/i18n/LocaleProvider";
import { ToggleButton } from "@/shared/ui";

type ReadingViewToggleProps = {
  pressed: boolean;
  onPressedChange: (nextPressed: boolean) => void;
  shortcutHint?: string;
  className?: string;
};

export function ReadingViewToggle({
  pressed,
  onPressedChange,
  shortcutHint = "R",
  className,
}: ReadingViewToggleProps) {
  const { t } = useI18n();

  return (
    <ToggleButton
      size="sm"
      label={t("common.readingView")}
      pressed={pressed}
      className={className}
      onPressedChange={onPressedChange}
      trailing={
        <span className="rounded-full border border-current/20 px-1.5 py-0.5 text-[0.62rem] leading-none opacity-80">
          {shortcutHint}
        </span>
      }
    />
  );
}
