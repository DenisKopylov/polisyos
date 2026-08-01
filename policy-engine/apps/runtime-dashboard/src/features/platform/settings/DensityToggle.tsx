import { AlignJustify, Minimize2, Rows3 } from "lucide-react";

import { useDensity } from "@/app/providers/DensityProvider";
import type { Density } from "@/app/state/usePreferencesStore";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { SegmentedControl } from "@polisyos/atlas-ui";

const DENSITY_OPTIONS = [
  "comfortable",
  "compact",
  "condensed",
] as const satisfies readonly Density[];

const DENSITY_ICONS: Record<Density, typeof AlignJustify> = {
  comfortable: AlignJustify,
  compact: Rows3,
  condensed: Minimize2,
};

export function DensityToggle() {
  const { density, setDensity } = useDensity();
  const { t } = useI18n();

  return (
    <section
      aria-labelledby="appearance-density-heading"
      className="space-y-3"
      data-testid="density-toggle"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3
            id="appearance-density-heading"
            className="text-sm font-semibold tracking-tight"
          >
            {t("pages.platform.appearance.densityLabel")}
          </h3>
          <p className="text-muted max-w-2xl text-xs leading-relaxed">
            {t("pages.platform.appearance.densityHint")}
          </p>
        </div>
        <span className="text-muted border-line rounded-full border px-3 py-1 text-[0.68rem] font-semibold tracking-[0.16em] uppercase">
          {t("pages.platform.appearance.densityShortcut")}
        </span>
      </div>

      <SegmentedControl
        ariaLabel={t("pages.platform.appearance.densityLabel")}
        className="md:grid-cols-3"
        value={density}
        onValueChange={setDensity}
        options={DENSITY_OPTIONS.map((option) => {
          const Icon = DENSITY_ICONS[option];
          return {
            icon: <Icon size={16} />,
            label: t(`pages.platform.appearance.densityOptions.${option}`),
            value: option,
          };
        })}
      />
    </section>
  );
}
