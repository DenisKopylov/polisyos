import { Link } from "react-router-dom";

import JsonPreview from "../shared/JsonPreview";
import StatusBadge from "../shared/StatusBadge";
import type { NodeDebugPayload, RunNodesPayload } from "../../api/validators";
import { formatDate, formatDuration } from "../../lib/utils";

function statusKind(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "completed" || normalized === "ok") {
    return "ok" as const;
  }
  if (normalized === "fail" || normalized === "failed") {
    return "fail" as const;
  }
  if (normalized === "running" || normalized === "skip") {
    return "warn" as const;
  }
  return "unknown" as const;
}

type NodeDebugPanelProps = {
  nodes: RunNodesPayload["nodes"];
  selectedAlias: string | null;
  onSelectAlias: (alias: string) => void;
  debugData: NodeDebugPayload["debug"] | null;
};

export default function NodeDebugPanel({
  nodes,
  selectedAlias,
  onSelectAlias,
  debugData,
}: NodeDebugPanelProps) {
  const nodeList = nodes ?? [];

  const inputArtifactIds = debugData?.record.input_artifact_ids ?? [];
  const outputArtifactIds = debugData?.record.output_artifact_ids ?? [];
  const timelineEvents = debugData?.timeline_events ?? [];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-panel p-3">
        <label className="text-sm font-medium" htmlFor="node-alias-select">
          Node alias
        </label>
        <select
          id="node-alias-select"
          value={selectedAlias ?? ""}
          onChange={(event) => onSelectAlias(event.target.value)}
          className="rounded-lg border border-line bg-panel px-2 py-1 text-sm"
        >
          {nodeList.map((node) => (
            <option key={node.alias} value={node.alias}>
              {node.alias}
            </option>
          ))}
        </select>
      </div>

      {debugData ? (
        <>
          <div className="rounded-xl border border-line bg-panel p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold">{debugData.record.alias}</p>
                <p className="font-mono text-xs text-muted">{debugData.record.node_id ?? "-"}</p>
              </div>
              <StatusBadge label={debugData.record.status} kind={statusKind(debugData.record.status)} />
            </div>

            <div className="grid gap-2 md:grid-cols-4">
              <div className="rounded-lg border border-line bg-canvas/30 px-2 py-1 text-sm">
                <p className="text-xs text-muted">Duration</p>
                <p className="font-semibold">{formatDuration(debugData.record.duration_ms)}</p>
              </div>
              <div className="rounded-lg border border-line bg-canvas/30 px-2 py-1 text-sm">
                <p className="text-xs text-muted">Cache hits</p>
                <p className="font-semibold">{debugData.cache_hits}</p>
              </div>
              <div className="rounded-lg border border-line bg-canvas/30 px-2 py-1 text-sm">
                <p className="text-xs text-muted">Cache stores</p>
                <p className="font-semibold">{debugData.cache_stores}</p>
              </div>
              <div className="rounded-lg border border-line bg-canvas/30 px-2 py-1 text-sm">
                <p className="text-xs text-muted">Cache bypasses</p>
                <p className="font-semibold">{debugData.cache_bypasses}</p>
              </div>
            </div>

            {debugData.record.error_code ? (
              <div className="mt-2 rounded-lg border border-danger/30 bg-danger/5 p-2 text-sm text-danger">
                <p className="font-mono">{debugData.record.error_code}</p>
                <p>{debugData.record.error_message ?? "Node failed"}</p>
              </div>
            ) : null}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-line bg-panel p-3">
              <p className="mb-2 text-xs uppercase text-muted">Input artifacts</p>
              {inputArtifactIds.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {inputArtifactIds.map((artifactId) => (
                    <Link key={artifactId} to={`/artifacts/${artifactId}`} className="font-mono text-xs underline">
                      {artifactId}
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted">No inputs captured.</p>
              )}
            </div>

            <div className="rounded-xl border border-line bg-panel p-3">
              <p className="mb-2 text-xs uppercase text-muted">Output artifacts</p>
              {outputArtifactIds.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {outputArtifactIds.map((artifactId) => (
                    <Link key={artifactId} to={`/artifacts/${artifactId}`} className="font-mono text-xs underline">
                      {artifactId}
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted">No outputs captured.</p>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-line bg-panel p-3">
            <p className="mb-2 text-xs uppercase text-muted">Timeline events ({timelineEvents.length})</p>
            {timelineEvents.length > 0 ? (
              <ol className="space-y-2">
                {timelineEvents.map((event) => (
                  <li key={`${event.index}-${event.event}`} className="rounded-lg border border-line bg-canvas/20 p-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <StatusBadge label={event.event} kind={statusKind(event.event)} />
                        <span className="text-xs text-muted">{event.phase}</span>
                      </div>
                      <span className="text-xs text-muted">{formatDate(event.timestamp)}</span>
                    </div>
                    {Object.keys(event.metrics ?? {}).length > 0 ? (
                      <div className="mt-2">
                        <JsonPreview data={event.metrics} />
                      </div>
                    ) : null}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-muted">No timeline events for this alias.</p>
            )}
          </div>

          {Object.keys(debugData.record.error_details ?? {}).length > 0 ? (
            <div className="rounded-xl border border-line bg-panel p-3">
              <p className="mb-1 text-xs uppercase text-muted">Error details</p>
              <JsonPreview data={debugData.record.error_details} />
            </div>
          ) : null}
        </>
      ) : (
        <div className="rounded-xl border border-dashed border-line bg-canvas/30 p-3 text-sm text-muted">
          Node debug data is unavailable.
        </div>
      )}
    </div>
  );
}
