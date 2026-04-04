import { Select } from "@/shared/ui";

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
  return (
    <div className="bg-canvas/40 border-line flex flex-wrap items-center gap-3 rounded-xl border p-3">
      <label className="inline-flex items-center gap-2 text-sm font-medium">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => onToggle(event.target.checked)}
          className="border-line h-4 w-4 rounded"
        />
        Show uncertainty bounds
      </label>

      <label className="text-muted inline-flex items-center gap-2 text-sm">
        Method
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
    </div>
  );
}
