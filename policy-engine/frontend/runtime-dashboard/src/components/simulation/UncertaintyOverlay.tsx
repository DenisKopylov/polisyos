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
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-canvas/40 p-3">
      <label className="inline-flex items-center gap-2 text-sm font-medium">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => onToggle(event.target.checked)}
          className="h-4 w-4 rounded border-line"
        />
        Show uncertainty bounds
      </label>

      <label className="inline-flex items-center gap-2 text-sm text-muted">
        Method
        <select
          value={selectedMethod}
          onChange={(event) => onMethodChange(event.target.value)}
          className="rounded-lg border border-line bg-panel px-2 py-1 text-sm"
        >
          {methods.map((method) => (
            <option key={method} value={method}>
              {method}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
