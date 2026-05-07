import {
  AUTHORSHIP_HIGHLIGHT_MODES,
  useAuthorship,
  type AuthorshipHighlightMode,
} from "@/shared/ui/authored-text";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { SegmentedControl } from "@/shared/ui";

const AUTHORSHIP_OPTIONS =
  AUTHORSHIP_HIGHLIGHT_MODES satisfies readonly AuthorshipHighlightMode[];

export function AuthorshipHighlightToggle() {
  const { highlightMode, setHighlightMode } = useAuthorship();
  const { t } = useI18n();

  return (
    <section
      aria-labelledby="appearance-authorship-heading"
      className="space-y-3"
      data-testid="authorship-highlight-toggle"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3
            id="appearance-authorship-heading"
            className="text-sm font-semibold tracking-tight"
          >
            {t("pages.platform.appearance.authorshipLabel")}
          </h3>
          <p className="text-muted max-w-2xl text-xs leading-relaxed">
            {t("pages.platform.appearance.authorshipHint")}
          </p>
        </div>
        <span className="text-muted border-line rounded-full border px-3 py-1 text-[0.68rem] font-semibold tracking-[0.16em] uppercase">
          {t("pages.platform.appearance.authorshipShortcut")}
        </span>
      </div>

      <SegmentedControl
        ariaLabel={t("pages.platform.appearance.authorshipLabel")}
        className="md:grid-cols-3"
        value={highlightMode}
        onValueChange={setHighlightMode}
        options={AUTHORSHIP_OPTIONS.map((option) => ({
          label: t(`pages.platform.appearance.authorshipOptions.${option}`),
          value: option,
        }))}
      />
    </section>
  );
}
