import { LaptopMinimal, MoonStar, SunMedium } from "lucide-react";

import { useTheme, type ThemePreference } from "@/app/providers/ThemeProvider";
import { useI18n } from "@/i18n/LocaleProvider";
import { SegmentedControl } from "@/shared/ui";

const THEME_ICONS = {
  dark: MoonStar,
  light: SunMedium,
  system: LaptopMinimal,
} as const;

const THEME_OPTIONS = [
  "light",
  "dark",
  "system",
] as const satisfies readonly ThemePreference[];

export function ThemeToggle() {
  const { isSystemTheme, resolvedTheme, setTheme, theme } = useTheme();
  const { t } = useI18n();

  return (
    <section
      aria-labelledby="appearance-theme-heading"
      className="space-y-3"
      data-testid="theme-toggle"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3
            id="appearance-theme-heading"
            className="text-sm font-semibold tracking-tight"
          >
            {t("pages.platform.appearance.themeLabel")}
          </h3>
          <p className="text-muted max-w-2xl text-xs leading-relaxed">
            {isSystemTheme
              ? t("pages.platform.appearance.themeResolved", {
                  mode: t(
                    `pages.platform.appearance.themeOptions.${resolvedTheme}`,
                  ).toLowerCase(),
                })
              : t("pages.platform.appearance.themeHint")}
          </p>
        </div>
        <span className="text-muted border-line rounded-full border px-3 py-1 text-[0.68rem] font-semibold tracking-[0.16em] uppercase">
          {t("pages.platform.appearance.themeShortcut")}
        </span>
      </div>

      <SegmentedControl
        ariaLabel={t("pages.platform.appearance.themeLabel")}
        className="md:grid-cols-3"
        value={theme}
        onValueChange={setTheme}
        options={THEME_OPTIONS.map((option) => {
          const Icon = THEME_ICONS[option];
          return {
            icon: <Icon size={16} />,
            label: t(`pages.platform.appearance.themeOptions.${option}`),
            value: option,
          };
        })}
      />
    </section>
  );
}
