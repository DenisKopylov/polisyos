import { SlidersHorizontal } from "lucide-react";

import { useDensity } from "@/app/providers/DensityProvider";
import { useTheme } from "@/app/providers/ThemeProvider";
import { readWorkspaceAppearancePreferences } from "@/app/workspaces";
import { useI18n } from "@/i18n/LocaleProvider";
import { useAuthorship } from "@/shared/ui/authored-text";
import { Card } from "@/shared/ui";

import { AuthorshipHighlightToggle } from "./AuthorshipHighlightToggle";
import { DensityToggle } from "./DensityToggle";
import { ThemeToggle } from "./ThemeToggle";

export function AppearanceSection() {
  const { density } = useDensity();
  const { highlightMode } = useAuthorship();
  const { resolvedTheme } = useTheme();
  const { t } = useI18n();
  const persistedAppearance = readWorkspaceAppearancePreferences();
  const persistedTheme =
    persistedAppearance.theme === "system"
      ? resolvedTheme
      : persistedAppearance.theme;
  const persistedDensity = persistedAppearance.density || density;

  return (
    <Card className="space-y-6" data-testid="platform-appearance-section">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-muted text-xs font-semibold tracking-[0.24em] uppercase">
            {t("commandPalette.appearance")}
          </p>
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="text-muted" size={16} />
            <h2 className="text-lg font-semibold">
              {t("pages.platform.appearance.title")}
            </h2>
          </div>
          <p className="text-muted max-w-3xl text-sm leading-relaxed">
            {t("pages.platform.appearance.subtitle")}
          </p>
        </div>

        <div className="border-line text-muted inline-flex items-center gap-2 rounded-full border bg-[var(--chip-bg)] px-3 py-1.5 text-[0.68rem] font-semibold tracking-[0.16em] uppercase">
          <span>{t("pages.platform.appearance.synced")}</span>
          <span>·</span>
          <span>
            {t(`pages.platform.appearance.themeOptions.${persistedTheme}`)}
          </span>
          <span>·</span>
          <span>
            {t(`pages.platform.appearance.densityOptions.${persistedDensity}`)}
          </span>
          <span>·</span>
          <span>
            {t(`pages.platform.appearance.authorshipOptions.${highlightMode}`)}
          </span>
        </div>
      </div>

      <div className="space-y-6">
        <ThemeToggle />
        <DensityToggle />
        <AuthorshipHighlightToggle />
      </div>
    </Card>
  );
}
