import { Link } from "react-router-dom";

import { useI18n } from "@/i18n/LocaleProvider";

import { chartTheme } from "./chartTheme";

type LineageNode = {
  artifact_id: string;
  depth: number;
  kind?: string | null;
  status: string;
  role?: string | null;
  byte_size?: number;
};

type LineageEdge = {
  parent_artifact_id: string;
  child_artifact_id: string;
  role: string;
};

type LineageGraphProps = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  rootArtifactIds?: string[];
  maxNodesForGraph?: number;
};

const COL_WIDTH = 280;
const ROW_HEIGHT = 92;
const CARD_WIDTH = 220;
const CARD_HEIGHT = 66;
const PADDING_X = 32;
const PADDING_Y = 24;

function statusColor(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "ok") {
    return chartTheme.success;
  }
  if (
    normalized === "missing" ||
    normalized === "error" ||
    normalized === "fail"
  ) {
    return chartTheme.alert;
  }
  if (normalized === "partial") {
    return chartTheme.warning;
  }
  return chartTheme.neutral;
}

export default function LineageGraph({
  nodes,
  edges,
  rootArtifactIds = [],
  maxNodesForGraph = 220,
}: LineageGraphProps) {
  const { t } = useI18n();

  if (nodes.length === 0) {
    return (
      <p className="text-muted text-sm">{t("common.lineageGraph.empty")}</p>
    );
  }

  if (nodes.length > maxNodesForGraph) {
    return (
      <div className="bg-panel/70 border-line text-muted rounded-xl border p-4 text-sm">
        <p>
          {t("common.lineageGraph.threshold", {
            nodes: nodes.length,
            maxNodes: maxNodesForGraph,
          })}
        </p>
        <p className="mt-1">{t("common.lineageGraph.thresholdHint")}</p>
      </div>
    );
  }

  const sortedNodes = [...nodes].sort(
    (a, b) => a.depth - b.depth || a.artifact_id.localeCompare(b.artifact_id),
  );
  const columns = new Map<number, LineageNode[]>();
  for (const node of sortedNodes) {
    const bucket = columns.get(node.depth) ?? [];
    bucket.push(node);
    columns.set(node.depth, bucket);
  }

  const maxDepth = Math.max(...sortedNodes.map((node) => node.depth));
  const maxRows = Math.max(
    ...Array.from(columns.values()).map((bucket) => bucket.length),
  );
  const width = PADDING_X * 2 + (maxDepth + 1) * COL_WIDTH;
  const height = PADDING_Y * 2 + maxRows * ROW_HEIGHT;

  const positions = new Map<string, { x: number; y: number }>();
  for (const [depth, bucket] of columns.entries()) {
    bucket.forEach((node, index) => {
      const x = PADDING_X + depth * COL_WIDTH;
      const y = PADDING_Y + index * ROW_HEIGHT;
      positions.set(node.artifact_id, { x, y });
    });
  }

  return (
    <div className="bg-surface/80 border-line overflow-auto rounded-xl border p-2">
      <div className="relative" style={{ width, height }}>
        <svg
          className="absolute top-0 left-0"
          width={width}
          height={height}
          role="img"
          aria-label={t("common.lineageGraph.ariaLabel")}
        >
          {edges.map((edge) => {
            const source = positions.get(edge.parent_artifact_id);
            const target = positions.get(edge.child_artifact_id);
            if (!source || !target) {
              return null;
            }

            const x1 = source.x + CARD_WIDTH;
            const y1 = source.y + CARD_HEIGHT / 2;
            const x2 = target.x;
            const y2 = target.y + CARD_HEIGHT / 2;
            const mid = (x1 + x2) / 2;

            return (
              <path
                key={`${edge.parent_artifact_id}-${edge.child_artifact_id}-${edge.role}`}
                d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                stroke={chartTheme.axis}
                strokeWidth={1.5}
                fill="none"
              />
            );
          })}
        </svg>

        {sortedNodes.map((node) => {
          const position = positions.get(node.artifact_id);
          if (!position) {
            return null;
          }
          const isRoot = rootArtifactIds.includes(node.artifact_id);

          return (
            <div
              key={node.artifact_id}
              className="absolute rounded-xl border bg-white p-2 shadow-sm"
              style={{
                left: position.x,
                top: position.y,
                width: CARD_WIDTH,
                height: CARD_HEIGHT,
                borderColor: isRoot ? chartTheme.secondary : "var(--line)",
                boxShadow: isRoot
                  ? "0 0 0 1px rgba(37,87,167,0.35)"
                  : undefined,
              }}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-mono text-[11px]">
                  {node.artifact_id}
                </span>
                <span
                  className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase"
                  style={{
                    color: statusColor(node.status),
                    backgroundColor: "rgba(255,255,255,0.78)",
                  }}
                >
                  {node.status}
                </span>
              </div>
              <p className="mt-1 truncate text-[11px] text-[color:var(--chart-axis)]">
                {node.kind ?? t("common.lineageGraph.unknownKind")}
              </p>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-[11px] text-[color:var(--chart-axis)]">
                  {t("shared.ui.lineageGraph.depthValue", {
                    depth: node.depth,
                  })}
                </span>
                <Link
                  className="text-[11px] font-semibold underline"
                  to={`/artifacts/${node.artifact_id}`}
                >
                  {t("common.inspect")}
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
