import type { TrinityIntervention } from "@/lib/domain/trinity";

function formatValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value === null || value === undefined) {
    return "-";
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

type InterventionDetailProps = {
  intervention: TrinityIntervention;
  defaultOpen?: boolean;
};

export default function InterventionDetail({
  intervention,
  defaultOpen = false,
}: InterventionDetailProps) {
  const params = Object.entries(intervention.params);

  return (
    <details
      open={defaultOpen}
      className="bg-canvas/40 rounded-xl border border-line p-3 open:bg-panel"
    >
      <summary className="cursor-pointer list-none">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold">{intervention.id}</p>
            <p className="text-xs text-muted">{intervention.kind}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span>{intervention.targetLabel}</span>
            <span>|</span>
            <span>{intervention.scheduleLabel}</span>
            {intervention.enabled !== null ? (
              <span>| {intervention.enabled ? "enabled" : "disabled"}</span>
            ) : null}
          </div>
        </div>
      </summary>

      <div className="mt-3 space-y-2 border-t border-line pt-3">
        {intervention.priority !== null ? (
          <p className="text-xs text-muted">
            Priority: {intervention.priority}
          </p>
        ) : null}

        {params.length === 0 ? (
          <p className="text-sm text-muted">No parameters.</p>
        ) : (
          <div className="grid gap-2 md:grid-cols-2">
            {params.map(([key, value]) => (
              <div
                key={key}
                className="rounded-lg border border-line bg-panel p-2"
              >
                <p className="font-mono text-xs text-muted">{key}</p>
                <p className="text-sm font-medium">{formatValue(value)}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}
