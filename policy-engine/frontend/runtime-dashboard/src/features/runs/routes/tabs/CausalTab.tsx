import {
  createElement,
  useEffect,
  useMemo,
  useState,
  type ComponentType,
} from "react";
import { useParams } from "react-router-dom";

import { useRunDetails } from "@/api/hooks/useRunDetails";
import { useI18n } from "@/i18n/LocaleProvider";
import {
  markUiMilestone,
  measureUiLatency,
} from "@/shared/telemetry/performance";
import { Card, EmptyState, PanelSkeleton } from "@/shared/ui";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import {
  CausalGraphCanvas,
  IdentificationOverlay,
  TransportOverlay,
  AdjustmentSetHighlight,
  NodeDetailPanel,
  EdgeDetailPanel,
  PathAnalysisPanel,
  type CausalNodeData,
  type CausalEdgeData,
  type CausalPath,
  type LayoutAlgorithm,
  type OverlayMode,
} from "@/features/causal";
import {
  ForestPlot,
  DiDVisualization,
  SyntheticControlViz,
  RDDVisualization,
  BSTSVisualization,
  MetaLearnerViz,
} from "@/shared/charts";

// ---------------------------------------------------------------------------
// Stub: extract causal graph data from run artifacts
// In production this would come from a dedicated API endpoint or
// a well-known artifact kind. For now we look for the "causal_graph"
// artifact in the run details and parse its payload.
// ---------------------------------------------------------------------------

type CausalArtifactPayload = {
  adjustmentSet: string[];
  edges: CausalEdgeData[];
  methodData?: Record<string, unknown>;
  methodology?: string;
  nodes: CausalNodeData[];
  paths: CausalPath[];
};

function buildPathLabel(
  nodeIds: string[],
  nodeMap: Map<string, CausalNodeData>,
) {
  return nodeIds
    .map((nodeId) => nodeMap.get(nodeId)?.label ?? nodeId)
    .join(" -> ");
}

function deriveCausalPaths(
  nodes: CausalNodeData[],
  edges: CausalEdgeData[],
): CausalPath[] {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const outgoing = new Map<string, CausalEdgeData[]>();
  for (const edge of edges) {
    const current = outgoing.get(edge.source) ?? [];
    current.push(edge);
    outgoing.set(edge.source, current);
  }

  const paths: CausalPath[] = edges.map((edge) => ({
    edgeIds: [edge.id],
    id: `direct:${edge.id}`,
    label: buildPathLabel([edge.source, edge.target], nodeMap),
    nodeIds: [edge.source, edge.target],
    totalEffect: edge.estimate,
    type: "direct",
  }));

  const seen = new Set(paths.map((path) => path.id));
  for (const first of edges) {
    for (const second of outgoing.get(first.target) ?? []) {
      if (second.target === first.source) {
        continue;
      }
      const pathId = `indirect:${first.id}:${second.id}`;
      if (seen.has(pathId)) {
        continue;
      }
      const middleKind = nodeMap.get(first.target)?.kind;
      paths.push({
        edgeIds: [first.id, second.id],
        id: pathId,
        label: buildPathLabel(
          [first.source, first.target, second.target],
          nodeMap,
        ),
        nodeIds: [first.source, first.target, second.target],
        totalEffect:
          typeof first.estimate === "number" && typeof second.estimate === "number"
            ? first.estimate * second.estimate
            : undefined,
        type:
          middleKind === "confounder"
            ? "backdoor"
            : middleKind === "instrument"
              ? "frontdoor"
              : "indirect",
      });
      seen.add(pathId);
    }
  }

  return paths;
}

function extractCausalGraph(
  run:
    | {
        artifacts?: Array<{ kind?: string; payload?: unknown }> | null;
      }
    | Record<string, unknown>
    | null
    | undefined,
): CausalArtifactPayload | null {
  const artifacts = Array.isArray(
    (run as { artifacts?: unknown } | null | undefined)?.artifacts,
  )
    ? ((run as { artifacts: Array<{ kind?: string; payload?: unknown }> })
        .artifacts ?? [])
    : [];
  if (artifacts.length === 0) {
    return null;
  }

  const graphArtifact = artifacts.find(
    (a) => a.kind === "causal_graph" || a.kind === "causal_dag",
  );
  if (!graphArtifact?.payload || typeof graphArtifact.payload !== "object") {
    return null;
  }
  const p = graphArtifact.payload as Record<string, unknown>;
  const nodes = Array.isArray(p.nodes) ? (p.nodes as CausalNodeData[]) : [];
  const edges = Array.isArray(p.edges) ? (p.edges as CausalEdgeData[]) : [];
  const adjustmentSet = Array.isArray(p.adjustment_set)
    ? p.adjustment_set.filter((value): value is string => typeof value === "string")
    : nodes.filter((node) => node.inAdjustmentSet).map((node) => node.id);

  return {
    adjustmentSet,
    edges,
    methodology: (p.methodology as string) ?? undefined,
    methodData: (p.method_data as Record<string, unknown>) ?? undefined,
    nodes,
    paths: deriveCausalPaths(nodes, edges),
  };
}

// ---------------------------------------------------------------------------
// Method visualization dispatcher
// ---------------------------------------------------------------------------

function MethodVisualization({
  methodology,
  data,
}: {
  methodology?: string;
  data?: Record<string, unknown>;
}) {
  if (!methodology || !data) return null;
  const visualizationData = data as Record<string, unknown>;
  const renderVisualization = (
    Component: ComponentType<Record<string, unknown>>,
  ) => createElement(Component, visualizationData);

  switch (methodology) {
    case "did":
    case "difference_in_differences":
      return renderVisualization(
        DiDVisualization as unknown as ComponentType<Record<string, unknown>>,
      );
    case "synthetic_control":
    case "sc":
      return renderVisualization(
        SyntheticControlViz as unknown as ComponentType<Record<string, unknown>>,
      );
    case "rdd":
    case "regression_discontinuity":
      return renderVisualization(
        RDDVisualization as unknown as ComponentType<Record<string, unknown>>,
      );
    case "bsts":
    case "bayesian_structural_time_series":
      return renderVisualization(
        BSTSVisualization as unknown as ComponentType<Record<string, unknown>>,
      );
    case "meta_learner":
    case "cate":
      return renderVisualization(
        MetaLearnerViz as unknown as ComponentType<Record<string, unknown>>,
      );
    case "forest_plot":
    case "meta_analysis":
      return renderVisualization(
        ForestPlot as unknown as ComponentType<Record<string, unknown>>,
      );
    default:
      return (
        <Card className="p-4">
          <p className="text-muted text-sm">
            Method-specific visualization for "{methodology}" is not yet available.
          </p>
        </Card>
      );
  }
}

// ---------------------------------------------------------------------------
// Main tab content
// ---------------------------------------------------------------------------

function CausalTabContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const runDetailsQuery = useRunDetails(runId);
  const graph = useMemo(
    () => extractCausalGraph(runDetailsQuery.data?.run ?? null),
    [runDetailsQuery.data],
  );

  const [layout, setLayout] = useState<LayoutAlgorithm>("hierarchical");
  const [overlay, setOverlay] = useState<OverlayMode>("none");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);

  useEffect(() => {
    if (!graph) {
      return;
    }
    markUiMilestone("runs.causal.ready", {
      routeId: "runs.detail.causal",
      surface: "causal",
    });
    measureUiLatency({
      context: {
        routeId: "runs.detail.causal",
        surface: "causal",
      },
      endMark: "runs.causal.ready",
      metric: "time_to_causal_ms",
    });
  }, [graph]);

  if (runDetailsQuery.isLoading) {
    return <PanelSkeleton rows={6} />;
  }

  if (!graph || graph.nodes.length === 0) {
    return (
      <EmptyState
        title={t("causal.title")}
        body={t("causal.empty")}
      />
    );
  }

  const selectedNode = selectedNodeId
    ? graph.nodes.find((node) => node.id === selectedNodeId) ?? null
    : null;
  const selectedEdge = selectedEdgeId
    ? graph.edges.find((edge) => edge.id === selectedEdgeId) ?? null
    : null;
  const selectedPath = selectedPathId
    ? graph.paths.find((path) => path.id === selectedPathId) ?? null
    : null;

  return (
    <div className="space-y-6">
      {/* Main graph canvas */}
      <div className="relative min-h-[400px]">
        <CausalGraphCanvas
          nodes={graph.nodes}
          edges={graph.edges}
          adjustmentSet={graph.adjustmentSet}
          highlightedPath={selectedPath?.edgeIds ?? []}
          layoutAlgorithm={layout}
          overlay={overlay}
          onLayoutChange={setLayout}
          onOverlayChange={setOverlay}
          onNodeSelect={(nodeId) => {
            setSelectedNodeId(nodeId);
            setSelectedEdgeId(null);
          }}
          onEdgeSelect={(edgeId) => {
            setSelectedEdgeId(edgeId);
            setSelectedNodeId(null);
          }}
          showControls
        />

        {/* Overlays */}
        {overlay === "identification" && (
          <IdentificationOverlay
            edges={graph.edges}
            className="absolute top-4 right-4 z-10 w-64"
          />
        )}
        {overlay === "transport" && (
          <TransportOverlay
            edges={graph.edges}
            className="absolute top-4 right-4 z-10 w-72"
          />
        )}
        {overlay === "adjustment_set" && (
          <AdjustmentSetHighlight
            nodes={graph.nodes}
            adjustmentSet={graph.adjustmentSet}
            className="absolute top-4 right-4 z-10 w-72"
          />
        )}
      </div>

      {/* Detail panels */}
      <div className="grid gap-4 lg:grid-cols-2">
        {selectedNode && (
          <NodeDetailPanel
            node={selectedNode}
            edges={graph.edges}
            onClose={() =>
              setSelectedNodeId(null)
            }
          />
        )}
        {selectedEdge && (
          <EdgeDetailPanel
            edge={selectedEdge}
            onClose={() =>
              setSelectedEdgeId(null)
            }
          />
        )}
      </div>

      {/* Path analysis */}
      {graph.paths.length > 0 && (
        <PathAnalysisPanel
          nodes={graph.nodes}
          edges={graph.edges}
          paths={graph.paths}
          selectedPathId={selectedPathId}
          onPathSelect={setSelectedPathId}
          onClose={() => setSelectedPathId(null)}
        />
      )}

      {/* Method-specific visualization */}
      <MethodVisualization
        methodology={graph.methodology}
        data={graph.methodData}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab wrapper
// ---------------------------------------------------------------------------

export default function CausalTab() {
  const { t } = useI18n();
  const { runId } = useParams<{ runId: string }>();

  if (!runId) return null;

  return (
    <FeatureAsyncBoundary
      body={t("causal.subtitle")}
      feature="runs.causal"
      loading={<PanelSkeleton rows={6} />}
      resetKeys={[runId]}
      title={t("causal.title")}
    >
      <CausalTabContent runId={runId} />
    </FeatureAsyncBoundary>
  );
}
