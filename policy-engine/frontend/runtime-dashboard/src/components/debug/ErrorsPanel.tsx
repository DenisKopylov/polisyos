import JsonPreview from "../shared/JsonPreview";
import StatusBadge from "../shared/StatusBadge";
import type { RunErrorsPayload } from "../../api/validators";
import { formatDate } from "../../lib/utils";

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
  return "unknown" as const;
}

type ErrorsPanelProps = {
  errors: RunErrorsPayload["errors"];
};

export default function ErrorsPanel({ errors }: ErrorsPanelProps) {
  const errorItems = errors ?? [];

  const bySource = errorItems.reduce<Record<string, number>>((acc, item) => {
    acc[item.source] = (acc[item.source] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-line bg-panel p-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold">Run errors</h3>
          <span className="text-sm text-muted">{errorItems.length} total</span>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          {Object.entries(bySource).map(([source, count]) => (
            <span key={source} className="rounded-full border border-line bg-canvas/40 px-2 py-1">
              {source}: {count}
            </span>
          ))}
        </div>
      </div>

      {errorItems.length > 0 ? (
        <div className="space-y-2">
          {errorItems.map((error, index) => (
            <details key={`${error.code}-${index}`} className="rounded-xl border border-line bg-panel p-3">
              <summary className="cursor-pointer list-none">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <StatusBadge label={error.source} kind={sourceKind(error.source)} />
                    <span className="font-mono text-xs">{error.code}</span>
                    {error.node_alias ? <span className="text-xs text-muted">node={error.node_alias}</span> : null}
                  </div>
                  {error.timestamp ? <span className="text-xs text-muted">{formatDate(error.timestamp)}</span> : null}
                </div>
                <p className="mt-1 text-sm">{error.message}</p>
              </summary>
              {Object.keys(error.details ?? {}).length > 0 ? (
                <div className="mt-3 border-t border-line pt-3">
                  <JsonPreview data={error.details} />
                </div>
              ) : null}
            </details>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-line bg-canvas/30 p-3 text-sm text-muted">
          No errors were reported for this run.
        </div>
      )}
    </div>
  );
}
