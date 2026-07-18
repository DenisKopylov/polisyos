import { useI18n } from "@/shared/i18n/LocaleProvider";
import { SegmentedControl, Select, ToggleButton } from "@polisyos/atlas-ui";

type UncertaintyOverlayProps = {
  enabled: boolean;
  onToggle: (next: boolean) => void;
  methods: string[];
  selectedMethod: string;
  onMethodChange: (method: string) => void;
};

export default function UncertaintyOverlay({
  enabled,
  onToggle,
  methods,
  selectedMethod,
  onMethodChange,
}: UncertaintyOverlayProps) {
  const { t } = useI18n();
  const useSegmentedMethods = methods.length > 0 && methods.length <= 4;

  return (
    <div className="bg-canvas/40 border-line flex flex-wrap items-center gap-3 rounded-xl border p-3">
      <ToggleButton
        label="Show uncertainty bounds"
        pressed={enabled}
        size="sm"
        onPressedChange={onToggle}
      />

      {useSegmentedMethods ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted text-sm">
            {t("pages.artifacts.simulation.viewer.method")}
          </span>
          <SegmentedControl
            ariaLabel="Uncertainty method"
            layout="wrap"
            size="sm"
            value={selectedMethod}
            onValueChange={onMethodChange}
            options={methods.map((method) => ({
              label: method,
              value: method,
            }))}
          />
        </div>
      ) : (
        <label className="text-muted inline-flex items-center gap-2 text-sm">
          {t("pages.artifacts.simulation.viewer.method")}
          <Select
            value={selectedMethod}
            onChange={(event) => onMethodChange(event.target.value)}
            className="w-auto rounded-lg px-2 py-1"
          >
            {methods.map((method) => (
              <option key={method} value={method}>
                {method}
              </option>
            ))}
          </Select>
        </label>
      )}
    </div>
  );
}
