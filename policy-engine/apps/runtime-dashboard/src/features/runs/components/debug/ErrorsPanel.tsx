import type { RunErrorsPayload } from "@/api/validators";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatDate } from "@/shared/lib/utils";
import { Badge, JsonPreview } from "@/shared/ui";

function sourceKind(source: string) {
  if (source === "workflow_report") {
    return "fail" as const;
  }
  if (source === "trace") {
    return "warn" as const;
  }
  if (source === "manifest") {
    return "warn" as const;
  }
  return "neutral" as const;
}

type ErrorsPanelProps = {
  errors: RunErrorsPayload["errors"];
};

export default function ErrorsPanel({ errors }: ErrorsPanelProps) {
  const { t } = useI18n();
  const errorItems = errors ?? [];

  const bySource = errorItems.reduce<Record<string, number>>((acc, item) => {
    acc[item.source] = (acc[item.source] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-3">
      <div className="border-line bg-panel rounded-xl border p-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold">
            {t("panels.errors.title")}
          </h3>
          <span className="text-muted text-sm">
            {t("panels.errors.total", { count: errorItems.length })}
          </span>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          {Object.entries(bySource).map(([source, count]) => (
            <span
              key={source}
              className="bg-canvas/40 border-line rounded-full border px-2 py-1"
            >
              {source}: {count}
            </span>
          ))}
        </div>
      </div>

      {errorItems.length > 0 ? (
        <div className="space-y-2">
          {errorItems.map((error, index) => (
            <details
              key={`${error.code}-${index}`}
              className="border-line bg-panel rounded-xl border p-3"
            >
              <summary className="cursor-pointer list-none">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge kind={sourceKind(error.source)}>
                      {error.source}
                    </Badge>
                    <span className="font-mono text-xs">{error.code}</span>
                    {error.node_alias ? (
                      <span className="text-muted text-xs">
                        {t("panels.errors.node", { alias: error.node_alias })}
                      </span>
                    ) : null}
                  </div>
                  {error.timestamp ? (
                    <span className="text-muted text-xs">
                      {formatDate(error.timestamp)}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm">{error.message}</p>
              </summary>
              {Object.keys(error.details ?? {}).length > 0 ? (
                <div className="border-line mt-3 border-t pt-3">
                  <JsonPreview data={error.details} />
                </div>
              ) : null}
            </details>
          ))}
        </div>
      ) : (
        <div className="bg-canvas/30 border-line text-muted rounded-xl border border-dashed p-3 text-sm">
          {t("panels.errors.empty")}
        </div>
      )}
    </div>
  );
}
