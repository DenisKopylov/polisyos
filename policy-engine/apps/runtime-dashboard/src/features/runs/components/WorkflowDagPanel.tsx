import { Link } from "react-router-dom";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  normalizeWorkflow,
  type WorkflowNodeView,
} from "@/shared/lib/domain/workflow";
import { formatDuration, formatNumber } from "@/shared/lib/utils";
import { Badge, EmptyState } from "@polisyos/atlas-ui";
import { chartTheme } from "@/shared/ui";

type WorkflowDagPanelProps = {
  payload: unknown;
  runId: string;
};

const COL_WIDTH = 280;
const ROW_HEIGHT = 100;
const NODE_WIDTH = 220;
const NODE_HEIGHT = 72;
const PADDING_X = 28;
const PADDING_Y = 20;

function statusKind(
  status: WorkflowNodeView["status"],
): "ok" | "warn" | "fail" | "neutral" {
  if (status === "ok") {
    return "ok";
  }
  if (status === "skip") {
    return "warn";
  }
  if (status === "fail") {
    return "fail";
  }
  return "neutral";
}

function heatColor(heat: number): string {
  const clamped = Math.max(0, Math.min(1, heat));
  if (clamped >= 0.85) {
    return "color-mix(in srgb, var(--danger) 22%, transparent)";
  }
  if (clamped >= 0.6) {
    return "color-mix(in srgb, var(--warning) 18%, transparent)";
  }
  if (clamped >= 0.25) {
    return "color-mix(in srgb, var(--success) 14%, transparent)";
  }
  return "color-mix(in srgb, var(--muted) 8%, transparent)";
}

export default function WorkflowDagPanel({
  payload,
  runId,
}: WorkflowDagPanelProps) {
  const { t } = useI18n();
  const workflow = normalizeWorkflow(payload);
  if (!workflow.nodes.length) {
    return (
      <EmptyState
        title={t("panels.workflow.emptyTitle")}
        body={t("panels.workflow.emptyBody")}
      />
    );
  }

  const columns = new Map<number, WorkflowNodeView[]>();
  for (const node of workflow.nodes) {
    const bucket = columns.get(node.depth) ?? [];
    bucket.push(node);
    columns.set(node.depth, bucket);
  }

  const maxDepth = Math.max(...workflow.nodes.map((node) => node.depth), 0);
  const maxRows = Math.max(
    ...Array.from(columns.values()).map((rows) => rows.length),
    1,
  );
  const width = PADDING_X * 2 + (maxDepth + 1) * COL_WIDTH;
  const height = PADDING_Y * 2 + maxRows * ROW_HEIGHT;

  const positions = new Map<string, { x: number; y: number }>();
  for (const [depth, bucket] of columns.entries()) {
    bucket
      .sort((left, right) => left.alias.localeCompare(right.alias))
      .forEach((node, index) => {
        positions.set(node.alias, {
          x: PADDING_X + depth * COL_WIDTH,
          y: PADDING_Y + index * ROW_HEIGHT,
        });
      });
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-2 md:grid-cols-5">
        <div className="border-line rounded-xl border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.workflow.workflow")}
          </p>
          <p className="font-semibold">{workflow.summary.workflowId ?? "-"}</p>
        </div>
        <div className="border-line rounded-xl border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.workflow.status")}
          </p>
          <p className="font-semibold">{workflow.summary.status ?? "-"}</p>
        </div>
        <div className="border-line rounded-xl border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.workflow.nodesEdges")}
          </p>
          <p className="font-semibold">
            {formatNumber(workflow.summary.nodeCount)} /{" "}
            {formatNumber(workflow.summary.edgeCount)}
          </p>
        </div>
        <div className="border-line rounded-xl border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.workflow.criticalPath")}
          </p>
          <p className="font-semibold">
            {formatDuration(workflow.summary.criticalPathDurationMs)}
          </p>
        </div>
        <div className="border-line rounded-xl border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.workflow.errorPolicy")}
          </p>
          <p className="font-semibold">{workflow.summary.errorPolicy ?? "-"}</p>
        </div>
      </div>

      {workflow.notes.length ? (
        <div className="border-warning/30 bg-warning/5 text-warning rounded-xl border p-2 text-xs">
          {workflow.notes.join(" · ")}
        </div>
      ) : null}

      <div className="bg-surface/80 border-line overflow-auto rounded-xl border p-2">
        <div className="relative" style={{ width, height }}>
          <svg className="absolute top-0 left-0" width={width} height={height}>
            {workflow.edges.map((edge) => {
              const from = positions.get(edge.fromAlias);
              const to = positions.get(edge.toAlias);
              if (!from || !to) {
                return null;
              }
              const x1 = from.x + NODE_WIDTH;
              const y1 = from.y + NODE_HEIGHT / 2;
              const x2 = to.x;
              const y2 = to.y + NODE_HEIGHT / 2;
              const mid = (x1 + x2) / 2;

              return (
                <path
                  key={`${edge.fromAlias}-${edge.toAlias}`}
                  d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                  stroke={chartTheme.axis}
                  strokeWidth={1.4}
                  fill="none"
                />
              );
            })}
          </svg>

          {workflow.nodes.map((node) => {
            const position = positions.get(node.alias);
            if (!position) {
              return null;
            }
            return (
              <div
                key={node.alias}
                className="border-line absolute rounded-xl border p-2 shadow-sm"
                style={{
                  left: position.x,
                  top: position.y,
                  width: NODE_WIDTH,
                  height: NODE_HEIGHT,
                  background: heatColor(node.heat),
                }}
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="truncate text-xs font-semibold">{node.label}</p>
                  <Badge kind={statusKind(node.status)}>{node.status}</Badge>
                </div>
                <p className="text-muted truncate font-mono text-[11px]">
                  {node.nodeId ?? "-"}
                </p>
                <div className="text-muted mt-1 flex items-center justify-between text-[11px]">
                  <span>
                    {t("panels.workflow.depthValue", {
                      depth: formatNumber(node.depth),
                    })}
                  </span>
                  <span>{formatDuration(node.durationMs)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="border-line overflow-x-auto rounded-xl border">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="border-line text-muted border-b text-left text-xs tracking-wide uppercase">
              <th className="px-3 py-2">{t("panels.workflow.alias")}</th>
              <th className="px-3 py-2">{t("panels.workflow.status")}</th>
              <th className="px-3 py-2">{t("panels.workflow.depth")}</th>
              <th className="px-3 py-2">{t("panels.workflow.duration")}</th>
              <th className="px-3 py-2">{t("panels.workflow.dependsOn")}</th>
              <th className="px-3 py-2">{t("panels.workflow.debug")}</th>
            </tr>
          </thead>
          <tbody>
            {workflow.nodes.map((node) => (
              <tr
                key={node.alias}
                className="border-line/70 border-b align-top last:border-b-0"
              >
                <td className="px-3 py-3">
                  <p className="font-semibold">{node.label}</p>
                  <p className="text-muted font-mono text-xs">
                    {node.nodeId ?? "-"}
                  </p>
                  {node.errorCode ? (
                    <p className="text-danger mt-1 font-mono text-xs">
                      {node.errorCode}
                    </p>
                  ) : null}
                </td>
                <td className="px-3 py-3">
                  <Badge kind={statusKind(node.status)}>{node.status}</Badge>
                </td>
                <td className="px-3 py-3">{formatNumber(node.depth)}</td>
                <td className="px-3 py-3">{formatDuration(node.durationMs)}</td>
                <td className="px-3 py-3">
                  {node.dependsOn.length ? (
                    node.dependsOn.join(", ")
                  ) : (
                    <span className="text-muted">-</span>
                  )}
                </td>
                <td className="px-3 py-3">
                  <Link
                    to={`/runs/${runId}?tab=debug`}
                    className="text-xs underline"
                  >
                    {t("panels.workflow.openDebug")}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
