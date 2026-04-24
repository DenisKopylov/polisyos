import { useI18n } from "@/i18n/LocaleProvider";
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
  const { t } = useI18n();
  const params = Object.entries(intervention.params);

  return (
    <details
      open={defaultOpen}
      className="bg-canvas/40 border-line open:bg-panel rounded-xl border p-3"
    >
      <summary className="cursor-pointer list-none">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold">{intervention.id}</p>
            <p className="text-muted text-xs">{intervention.kind}</p>
          </div>
          <div className="text-muted flex flex-wrap items-center gap-2 text-xs">
            <span>{intervention.targetLabel}</span>
            <span>|</span>
            <span>{intervention.scheduleLabel}</span>
            {intervention.enabled !== null ? (
              <span>| {intervention.enabled ? "enabled" : "disabled"}</span>
            ) : null}
          </div>
        </div>
      </summary>

      <div className="border-line mt-3 space-y-2 border-t pt-3">
        {intervention.priority !== null ? (
          <p className="text-muted text-xs">
            {t("pages.artifacts.trinity.interventionPriority", {
              priority: intervention.priority,
            })}
          </p>
        ) : null}

        {params.length === 0 ? (
          <p className="text-muted text-sm">
            {t("pages.artifacts.trinity.noParameters")}
          </p>
        ) : (
          <div className="grid gap-2 md:grid-cols-2">
            {params.map(([key, value]) => (
              <div
                key={key}
                className="border-line bg-panel rounded-lg border p-2"
              >
                <p className="text-muted font-mono text-xs">{key}</p>
                <p className="text-sm font-medium">{formatValue(value)}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}
