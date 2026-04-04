import { Link } from "react-router-dom";

import type { NodeDebugPayload, RunNodesPayload } from "@/api/validators";
import { useI18n } from "@/i18n/LocaleProvider";
import { formatDate, formatDuration, formatNumber } from "@/lib/utils";
import { Badge, JsonPreview, Select } from "@/shared/ui";

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
  return "neutral" as const;
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
  const { t } = useI18n();
  const nodeList = nodes ?? [];

  const inputArtifactIds = debugData?.record.input_artifact_ids ?? [];
  const outputArtifactIds = debugData?.record.output_artifact_ids ?? [];
  const timelineEvents = debugData?.timeline_events ?? [];

  return (
    <div className="space-y-3">
      <div className="border-line bg-panel flex flex-wrap items-center gap-2 rounded-xl border p-3">
        <label className="text-sm font-medium" htmlFor="node-alias-select">
          {t("panels.nodeDebug.alias")}
        </label>
        <Select
          id="node-alias-select"
          value={selectedAlias ?? ""}
          onChange={(event) => onSelectAlias(event.target.value)}
          className="w-auto rounded-lg px-2 py-1"
        >
          {nodeList.map((node) => (
            <option key={node.alias} value={node.alias}>
              {node.alias}
            </option>
          ))}
        </Select>
      </div>

      {debugData ? (
        <>
          <div className="border-line bg-panel rounded-xl border p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold">
                  {debugData.record.alias}
                </p>
                <p className="text-muted font-mono text-xs">
                  {debugData.record.node_id ?? "-"}
                </p>
              </div>
              <Badge kind={statusKind(debugData.record.status)}>
                {debugData.record.status}
              </Badge>
            </div>

            <div className="grid gap-2 md:grid-cols-4">
              <div className="bg-canvas/30 border-line rounded-lg border px-2 py-1 text-sm">
                <p className="text-muted text-xs">
                  {t("panels.nodeDebug.duration")}
                </p>
                <p className="font-semibold">
                  {formatDuration(debugData.record.duration_ms)}
                </p>
              </div>
              <div className="bg-canvas/30 border-line rounded-lg border px-2 py-1 text-sm">
                <p className="text-muted text-xs">
                  {t("panels.nodeDebug.cacheHits")}
                </p>
                <p className="font-semibold">
                  {formatNumber(debugData.cache_hits)}
                </p>
              </div>
              <div className="bg-canvas/30 border-line rounded-lg border px-2 py-1 text-sm">
                <p className="text-muted text-xs">
                  {t("panels.nodeDebug.cacheStores")}
                </p>
                <p className="font-semibold">
                  {formatNumber(debugData.cache_stores)}
                </p>
              </div>
              <div className="bg-canvas/30 border-line rounded-lg border px-2 py-1 text-sm">
                <p className="text-muted text-xs">
                  {t("panels.nodeDebug.cacheBypasses")}
                </p>
                <p className="font-semibold">
                  {formatNumber(debugData.cache_bypasses)}
                </p>
              </div>
            </div>

            {debugData.record.error_code ? (
              <div className="border-danger/30 bg-danger/5 text-danger mt-2 rounded-lg border p-2 text-sm">
                <p className="font-mono">{debugData.record.error_code}</p>
                <p>
                  {debugData.record.error_message ??
                    t("panels.nodeDebug.nodeFailed")}
                </p>
              </div>
            ) : null}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="border-line bg-panel rounded-xl border p-3">
              <p className="text-muted mb-2 text-xs uppercase">
                {t("panels.nodeDebug.inputArtifacts")}
              </p>
              {inputArtifactIds.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {inputArtifactIds.map((artifactId) => (
                    <Link
                      key={artifactId}
                      to={`/artifacts/${artifactId}`}
                      className="font-mono text-xs underline"
                    >
                      {artifactId}
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-muted text-sm">
                  {t("panels.nodeDebug.noInputs")}
                </p>
              )}
            </div>

            <div className="border-line bg-panel rounded-xl border p-3">
              <p className="text-muted mb-2 text-xs uppercase">
                {t("panels.nodeDebug.outputArtifacts")}
              </p>
              {outputArtifactIds.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {outputArtifactIds.map((artifactId) => (
                    <Link
                      key={artifactId}
                      to={`/artifacts/${artifactId}`}
                      className="font-mono text-xs underline"
                    >
                      {artifactId}
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-muted text-sm">
                  {t("panels.nodeDebug.noOutputs")}
                </p>
              )}
            </div>
          </div>

          <div className="border-line bg-panel rounded-xl border p-3">
            <p className="text-muted mb-2 text-xs uppercase">
              {t("panels.nodeDebug.timelineEvents", {
                count: formatNumber(timelineEvents.length),
              })}
            </p>
            {timelineEvents.length > 0 ? (
              <ol className="space-y-2">
                {timelineEvents.map((event) => (
                  <li
                    key={`${event.index}-${event.event}`}
                    className="bg-canvas/20 border-line rounded-lg border p-2"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Badge kind={statusKind(event.event)}>
                          {event.event}
                        </Badge>
                        <span className="text-muted text-xs">
                          {event.phase}
                        </span>
                      </div>
                      <span className="text-muted text-xs">
                        {formatDate(event.timestamp)}
                      </span>
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
              <p className="text-muted text-sm">
                {t("panels.nodeDebug.noTimeline")}
              </p>
            )}
          </div>

          {Object.keys(debugData.record.error_details ?? {}).length > 0 ? (
            <div className="border-line bg-panel rounded-xl border p-3">
              <p className="text-muted mb-1 text-xs uppercase">
                {t("panels.nodeDebug.errorDetails")}
              </p>
              <JsonPreview data={debugData.record.error_details} />
            </div>
          ) : null}
        </>
      ) : (
        <div className="bg-canvas/30 border-line text-muted rounded-xl border border-dashed p-3 text-sm">
          {t("panels.nodeDebug.unavailable")}
        </div>
      )}
    </div>
  );
}
