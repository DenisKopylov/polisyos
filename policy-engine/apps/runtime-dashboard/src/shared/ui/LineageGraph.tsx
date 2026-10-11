import { Link } from "react-router-dom";

import { buildArtifactHref } from "@/features/artifacts/domain/searchParams";
import {
  evidenceArtifactRefKey,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";
import { useI18n } from "@/shared/i18n/LocaleProvider";

import { chartTheme } from "./chartTheme";

type LineageNode = {
  artifact_id: string;
  manifest_profile_sha256?: string | null;
  depth: number;
  kind?: string | null;
  media_type?: string | null;
  status: string;
  role?: string | null;
  byte_size?: number;
};

type LineageEdge = {
  parent_artifact_id: string;
  parent_manifest_profile_sha256?: string | null;
  child_artifact_id: string;
  child_manifest_profile_sha256?: string | null;
  role: string;
};

type LineageArtifactRef = {
  artifact_id: string;
  kind?: string | null;
  media_type?: string | null;
  manifest_profile_sha256?: string | null;
};

type LineageGraphProps = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  rootArtifactIds?: string[];
  rootArtifactRefs?: LineageArtifactRef[];
  maxNodesForGraph?: number;
};

const COL_WIDTH = 280;
const ROW_HEIGHT = 92;
const CARD_WIDTH = 220;
const CARD_HEIGHT = 66;
const PADDING_X = 32;
const PADDING_Y = 24;

export default function LineageGraph({
  nodes,
  edges,
  rootArtifactIds = [],
  rootArtifactRefs,
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

  const nodeRef = (node: LineageNode): EvidenceArtifactRef => ({
    artifact_id: node.artifact_id,
    kind: node.kind ?? null,
    media_type: node.media_type ?? null,
    manifest_profile_sha256: node.manifest_profile_sha256 ?? null,
  });
  const nodeKey = (node: LineageNode) => evidenceArtifactRefKey(nodeRef(node));
  const hasTypedRootRefs = Boolean(rootArtifactRefs?.length);
  const rootKeys = new Set(
    rootArtifactRefs?.map((ref) => evidenceArtifactRefKey(ref)) ?? [],
  );
  const rootIds = new Set(rootArtifactIds);
  const sortedNodes = [...nodes].sort(
    (a, b) =>
      a.depth - b.depth ||
      a.artifact_id.localeCompare(b.artifact_id) ||
      (a.manifest_profile_sha256 ?? "").localeCompare(
        b.manifest_profile_sha256 ?? "",
      ) ||
      (a.kind ?? "").localeCompare(b.kind ?? "") ||
      (a.media_type ?? "").localeCompare(b.media_type ?? ""),
  );
  const edgeNodeKey = (artifactId: string, profile?: string | null) => {
    const matches = sortedNodes.filter(
      (node) =>
        node.artifact_id === artifactId &&
        (node.manifest_profile_sha256 ?? null) === (profile ?? null),
    );
    return matches.length === 1 ? nodeKey(matches[0]!) : null;
  };
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
      positions.set(nodeKey(node), { x, y });
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
            const sourceKey = edgeNodeKey(
              edge.parent_artifact_id,
              edge.parent_manifest_profile_sha256,
            );
            const targetKey = edgeNodeKey(
              edge.child_artifact_id,
              edge.child_manifest_profile_sha256,
            );
            const source = sourceKey ? positions.get(sourceKey) : undefined;
            const target = targetKey ? positions.get(targetKey) : undefined;
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
                key={`${sourceKey}->${targetKey}:${edge.role}`}
                d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                stroke={chartTheme.axis}
                strokeWidth={1.5}
                fill="none"
              />
            );
          })}
        </svg>

        {sortedNodes.map((node) => {
          const identity = nodeKey(node);
          const position = positions.get(identity);
          if (!position) {
            return null;
          }
          const isRoot = hasTypedRootRefs
            ? rootKeys.has(identity)
            : rootIds.has(node.artifact_id);

          return (
            <div
              key={identity}
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
                    color: chartTheme.neutral,
                    backgroundColor: "rgba(255,255,255,0.78)",
                  }}
                >
                  {node.status}
                </span>
              </div>
              <p className="mt-1 truncate text-[11px] text-[color:var(--chart-axis)]">
                {node.kind ?? t("common.lineageGraph.unknownKind")}
              </p>
              {node.manifest_profile_sha256 ? (
                <p className="truncate font-mono text-[9px] text-[color:var(--chart-axis)]">
                  {node.manifest_profile_sha256}
                </p>
              ) : (
                <p className="truncate text-[9px] text-[color:var(--chart-axis)]">
                  {t("common.lineageGraph.unqualifiedProfile")}
                </p>
              )}
              <div className="mt-1 flex items-center justify-between">
                <span className="text-[11px] text-[color:var(--chart-axis)]">
                  {t("shared.ui.lineageGraph.depthValue", {
                    depth: node.depth,
                  })}
                </span>
                <Link
                  className="text-[11px] font-semibold underline"
                  to={buildArtifactHref(node.artifact_id, {
                    artifactRef: nodeRef(node),
                  })}
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
