import { Link } from "react-router-dom";

import { normalizeWorkflow, type WorkflowNodeView } from "../../lib/domain/workflow";
import { formatDuration } from "../../lib/utils";
import StatusBadge from "../shared/StatusBadge";
import EmptyState from "../shared/EmptyState";

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

function statusKind(status: WorkflowNodeView["status"]): "ok" | "warn" | "fail" | "unknown" {
  if (status === "ok") {
    return "ok";
  }
  if (status === "skip") {
    return "warn";
  }
  if (status === "fail") {
    return "fail";
  }
  return "unknown";
}

function heatColor(heat: number): string {
  const clamped = Math.max(0, Math.min(1, heat));
  if (clamped >= 0.85) {
    return "rgba(181, 36, 47, 0.22)";
  }
  if (clamped >= 0.6) {
    return "rgba(178, 118, 23, 0.18)";
  }
  if (clamped >= 0.25) {
    return "rgba(18, 128, 92, 0.14)";
  }
  return "rgba(94, 113, 135, 0.08)";
}

export default function WorkflowDagPanel({ payload, runId }: WorkflowDagPanelProps) {
  const workflow = normalizeWorkflow(payload);
  if (!workflow.nodes.length) {
    return <EmptyState title="Workflow graph is empty" body="No workflow nodes were provided for this run." />;
  }

  const columns = new Map<number, WorkflowNodeView[]>();
  for (const node of workflow.nodes) {
    const bucket = columns.get(node.depth) ?? [];
    bucket.push(node);
    columns.set(node.depth, bucket);
  }

  const maxDepth = Math.max(...workflow.nodes.map((node) => node.depth), 0);
  const maxRows = Math.max(...Array.from(columns.values()).map((rows) => rows.length), 1);
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
        <div className="rounded-xl border border-line p-2 text-sm">
          <p className="text-xs uppercase text-muted">Workflow</p>
          <p className="font-semibold">{workflow.summary.workflowId ?? "-"}</p>
        </div>
        <div className="rounded-xl border border-line p-2 text-sm">
          <p className="text-xs uppercase text-muted">Status</p>
          <p className="font-semibold">{workflow.summary.status ?? "-"}</p>
        </div>
        <div className="rounded-xl border border-line p-2 text-sm">
          <p className="text-xs uppercase text-muted">Nodes / Edges</p>
          <p className="font-semibold">
            {workflow.summary.nodeCount} / {workflow.summary.edgeCount}
          </p>
        </div>
        <div className="rounded-xl border border-line p-2 text-sm">
          <p className="text-xs uppercase text-muted">Critical path</p>
          <p className="font-semibold">{formatDuration(workflow.summary.criticalPathDurationMs)}</p>
        </div>
        <div className="rounded-xl border border-line p-2 text-sm">
          <p className="text-xs uppercase text-muted">Error policy</p>
          <p className="font-semibold">{workflow.summary.errorPolicy ?? "-"}</p>
        </div>
      </div>

      {workflow.notes.length ? (
        <div className="rounded-xl border border-warning/30 bg-warning/5 p-2 text-xs text-warning">
          {workflow.notes.join(" · ")}
        </div>
      ) : null}

      <div className="overflow-auto rounded-xl border border-line bg-[#f7fbff] p-2">
        <div className="relative" style={{ width, height }}>
          <svg className="absolute left-0 top-0" width={width} height={height}>
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
                  stroke="#99a9bf"
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
                className="absolute rounded-xl border border-line p-2 shadow-sm"
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
                  <StatusBadge label={node.status} kind={statusKind(node.status)} />
                </div>
                <p className="truncate font-mono text-[11px] text-muted">{node.nodeId ?? "-"}</p>
                <div className="mt-1 flex items-center justify-between text-[11px] text-muted">
                  <span>d={node.depth}</span>
                  <span>{formatDuration(node.durationMs)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-3 py-2">Alias</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Depth</th>
              <th className="px-3 py-2">Duration</th>
              <th className="px-3 py-2">Depends on</th>
              <th className="px-3 py-2">Debug</th>
            </tr>
          </thead>
          <tbody>
            {workflow.nodes.map((node) => (
              <tr key={node.alias} className="border-b border-line/70 align-top last:border-b-0">
                <td className="px-3 py-3">
                  <p className="font-semibold">{node.label}</p>
                  <p className="font-mono text-xs text-muted">{node.nodeId ?? "-"}</p>
                  {node.errorCode ? (
                    <p className="mt-1 font-mono text-xs text-danger">{node.errorCode}</p>
                  ) : null}
                </td>
                <td className="px-3 py-3">
                  <StatusBadge label={node.status} kind={statusKind(node.status)} />
                </td>
                <td className="px-3 py-3">{node.depth}</td>
                <td className="px-3 py-3">{formatDuration(node.durationMs)}</td>
                <td className="px-3 py-3">
                  {node.dependsOn.length ? node.dependsOn.join(", ") : <span className="text-muted">-</span>}
                </td>
                <td className="px-3 py-3">
                  <Link to={`/runs/${runId}?tab=debug`} className="text-xs underline">
                    open debug
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
