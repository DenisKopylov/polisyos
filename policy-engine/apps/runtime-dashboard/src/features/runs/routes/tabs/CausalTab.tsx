import {
  createElement,
  useEffect,
  useMemo,
  useState,
  type ComponentType,
} from "react";
import { useParams } from "react-router-dom";

import { useRunDetails } from "@/api/hooks/useRunDetails";
import { useAuthz } from "@/app/authz/AuthzProvider";
import {
  createAuthorityLocalStateEnvelopeFamily,
  type AuthorityLocalScope,
} from "@/app/offline/authorityLocalState";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  markUiMilestone,
  measureUiLatency,
} from "@/shared/telemetry/performance";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Label,
  PanelSkeleton,
  Select,
} from "@polisyos/atlas-ui";
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
  type CausalNodeKind,
  type CausalPath,
  type LayoutAlgorithm,
  type OverlayMode,
  createCausalDraftIdentificationDisplay,
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

export type CausalArtifactPayload = {
  adjustmentSet: string[];
  edges: CausalEdgeData[];
  methodData?: Record<string, unknown>;
  methodology?: string;
  nodes: CausalNodeData[];
  paths: CausalPath[];
};

const CAUSAL_NODE_KINDS: CausalNodeKind[] = [
  "treatment",
  "outcome",
  "confounder",
  "mediator",
  "collider",
  "instrument",
  "selection",
];

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
          typeof first.estimate === "number" &&
          typeof second.estimate === "number"
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

function asCandidateCausalGraph(
  graph: CausalArtifactPayload,
): CausalArtifactPayload {
  const nodes = graph.nodes.map(({ description, id, kind, label }) => ({
    description,
    id,
    kind,
    label,
  }));
  const edges = graph.edges.map(
    ({ id, source, target }): CausalEdgeData => ({
      id,
      source,
      status: createCausalDraftIdentificationDisplay("unidentified"),
      target,
    }),
  );
  return {
    adjustmentSet: [],
    edges,
    nodes,
    paths: deriveCausalPaths(nodes, edges),
  };
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
    ? p.adjustment_set.filter(
        (value): value is string => typeof value === "string",
      )
    : nodes.filter((node) => node.inAdjustmentSet).map((node) => node.id);

  return asCandidateCausalGraph({
    adjustmentSet,
    edges,
    methodology: (p.methodology as string) ?? undefined,
    methodData: (p.method_data as Record<string, unknown>) ?? undefined,
    nodes,
    paths: [],
  });
}

function buildFallbackCausalGraph(): CausalArtifactPayload {
  const nodes: CausalNodeData[] = [
    {
      id: "policy",
      kind: "treatment",
      label: "Policy",
    },
    {
      id: "outcome",
      kind: "outcome",
      label: "Outcome",
    },
  ];
  const edges: CausalEdgeData[] = [
    {
      id: "policy-outcome",
      source: "policy",
      status: createCausalDraftIdentificationDisplay("unidentified"),
      target: "outcome",
    },
  ];

  return {
    adjustmentSet: [],
    edges,
    nodes,
    paths: deriveCausalPaths(nodes, edges),
  };
}

function nextDraftId(label: string, existingIds: Set<string>) {
  const base =
    label
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "node";
  let candidate = base;
  let index = 2;
  while (existingIds.has(candidate)) {
    candidate = `${base}-${index}`;
    index += 1;
  }
  return candidate;
}

type StoredCausalNode = Readonly<{
  description?: string;
  id: string;
  kind: CausalNodeKind;
  label: string;
}>;

type StoredCausalEdge = Readonly<{
  id: string;
  source: string;
  target: string;
}>;

type StoredCausalGraph = Readonly<{
  edges: StoredCausalEdge[];
  nodes: StoredCausalNode[];
}>;

type CausalDraftStorage = Readonly<{
  getItem: (key: string) => string | null;
  removeItem: (key: string) => void;
  setItem: (key: string, value: string) => void;
}>;

const CAUSAL_DRAFT_FAMILY = "causal-draft" as const;
const CAUSAL_DRAFT_TTL_MS = 24 * 60 * 60 * 1_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, keys: string[]) {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function parseStoredCausalNode(value: unknown): StoredCausalNode | null {
  if (!isRecord(value)) {
    return null;
  }
  const hasDescription = Object.hasOwn(value, "description");
  if (
    !hasExactKeys(
      value,
      hasDescription
        ? ["description", "id", "kind", "label"]
        : ["id", "kind", "label"],
    ) ||
    !isNonEmptyString(value.id) ||
    !isNonEmptyString(value.label) ||
    !CAUSAL_NODE_KINDS.includes(value.kind as CausalNodeKind) ||
    (hasDescription && typeof value.description !== "string")
  ) {
    return null;
  }
  return {
    ...(hasDescription ? { description: value.description as string } : {}),
    id: value.id,
    kind: value.kind as CausalNodeKind,
    label: value.label,
  };
}

function parseStoredCausalEdge(value: unknown): StoredCausalEdge | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["id", "source", "target"]) ||
    !isNonEmptyString(value.id) ||
    !isNonEmptyString(value.source) ||
    !isNonEmptyString(value.target)
  ) {
    return null;
  }
  return { id: value.id, source: value.source, target: value.target };
}

function parseStoredCausalGraph(value: unknown): StoredCausalGraph | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["edges", "nodes"]) ||
    !Array.isArray(value.nodes) ||
    !Array.isArray(value.edges)
  ) {
    return null;
  }
  const nodes: StoredCausalNode[] = [];
  const nodeIds = new Set<string>();
  for (const candidate of value.nodes) {
    const node = parseStoredCausalNode(candidate);
    if (!node || nodeIds.has(node.id)) {
      return null;
    }
    nodes.push(node);
    nodeIds.add(node.id);
  }
  const edges: StoredCausalEdge[] = [];
  const edgeIds = new Set<string>();
  for (const candidate of value.edges) {
    const edge = parseStoredCausalEdge(candidate);
    if (
      !edge ||
      edgeIds.has(edge.id) ||
      !nodeIds.has(edge.source) ||
      !nodeIds.has(edge.target)
    ) {
      return null;
    }
    edges.push(edge);
    edgeIds.add(edge.id);
  }
  return { edges, nodes };
}

function encodeStoredCausalGraph(
  graph: CausalArtifactPayload,
): StoredCausalGraph | null {
  const projected: StoredCausalGraph = {
    edges: graph.edges.map(({ id, source, target }) => ({
      id,
      source,
      target,
    })),
    nodes: graph.nodes.map(({ description, id, kind, label }) => ({
      ...(description === undefined ? {} : { description }),
      id,
      kind,
      label,
    })),
  };
  return parseStoredCausalGraph(projected);
}

function decodeStoredCausalGraph(value: unknown): CausalArtifactPayload | null {
  const stored = parseStoredCausalGraph(value);
  if (!stored) {
    return null;
  }
  const nodes: CausalNodeData[] = stored.nodes.map((node) => ({ ...node }));
  const edges: CausalEdgeData[] = stored.edges.map((edge) => ({
    ...edge,
    status: createCausalDraftIdentificationDisplay("unidentified"),
  }));
  return {
    adjustmentSet: [],
    edges,
    nodes,
    paths: deriveCausalPaths(nodes, edges),
  };
}

function browserCausalDraftStorage(): CausalDraftStorage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function createCausalDraftPersistence(config?: {
  clock?: () => Date;
  storage?: () => CausalDraftStorage | null;
}) {
  const owner = createAuthorityLocalStateEnvelopeFamily({
    clock: config?.clock ?? (() => new Date()),
    codec: {
      decode: decodeStoredCausalGraph,
      encode: encodeStoredCausalGraph,
    },
    family: CAUSAL_DRAFT_FAMILY,
    ttlMs: CAUSAL_DRAFT_TTL_MS,
    version: 1,
  });
  const storageResolver = config?.storage ?? browserCausalDraftStorage;

  function resolveStorage(): CausalDraftStorage | null {
    try {
      return storageResolver();
    } catch {
      return null;
    }
  }

  function key(
    scope: AuthorityLocalScope | null | undefined,
    runId: string,
  ) {
    return owner.key({ scope, slot: runId });
  }

  function read(
    scope: AuthorityLocalScope | null | undefined,
    runId: string,
  ): CausalArtifactPayload | null {
    const physicalKey = key(scope, runId);
    if (!physicalKey) {
      return null;
    }
    try {
      const raw = resolveStorage()?.getItem(physicalKey);
      if (!raw) {
        return null;
      }
      return owner.decode({
        envelope: JSON.parse(raw) as unknown,
        fallback: null,
        scope,
        slot: runId,
      });
    } catch {
      return null;
    }
  }

  function write(
    scope: AuthorityLocalScope | null | undefined,
    runId: string,
    graph: CausalArtifactPayload,
  ): boolean {
    const issued = owner.encode({ scope, slot: runId, value: graph });
    if (!issued) {
      return false;
    }
    const storage = resolveStorage();
    if (!storage) {
      return false;
    }
    try {
      storage.setItem(issued.key, JSON.stringify(issued.envelope));
      return true;
    } catch {
      return false;
    }
  }

  function remove(
    scope: AuthorityLocalScope | null | undefined,
    runId: string,
  ): boolean {
    const physicalKey = key(scope, runId);
    if (!physicalKey) {
      return false;
    }
    try {
      const storage = resolveStorage();
      if (!storage) {
        return false;
      }
      storage.removeItem(physicalKey);
      return true;
    } catch {
      return false;
    }
  }

  return Object.freeze({ key, read, remove, write });
}

const causalDraftPersistence = createCausalDraftPersistence();

function readStoredCausalDraft(
  scope: AuthorityLocalScope | null | undefined,
  runId: string,
) {
  return causalDraftPersistence.read(scope, runId);
}

function writeStoredCausalDraft(
  scope: AuthorityLocalScope | null | undefined,
  runId: string,
  graph: CausalArtifactPayload,
) {
  return causalDraftPersistence.write(scope, runId, graph);
}

function removeStoredCausalDraft(
  scope: AuthorityLocalScope | null | undefined,
  runId: string,
) {
  return causalDraftPersistence.remove(scope, runId);
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
  const { t } = useI18n();
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
        SyntheticControlViz as unknown as ComponentType<
          Record<string, unknown>
        >,
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
            {t("pages.runs.causal.methodUnavailable", { methodology })}
          </p>
        </Card>
      );
  }
}

// ---------------------------------------------------------------------------
// Main tab content
// ---------------------------------------------------------------------------

function CausalTabContent({
  runId,
  scope,
}: {
  runId: string;
  scope: AuthorityLocalScope | null;
}) {
  const { t } = useI18n();
  const runDetailsQuery = useRunDetails(runId);
  const graph = useMemo(
    () => extractCausalGraph(runDetailsQuery.data?.run ?? null),
    [runDetailsQuery.data],
  );
  const storedDraft = useMemo(
    () => (graph ? null : readStoredCausalDraft(scope, runId)),
    [graph, runId, scope],
  );
  const sourceGraph = useMemo(
    () => graph ?? storedDraft ?? buildFallbackCausalGraph(),
    [graph, storedDraft],
  );

  const [layout, setLayout] = useState<LayoutAlgorithm>("hierarchical");
  const [overlay, setOverlay] = useState<OverlayMode>("none");
  const [adversarialMode, setAdversarialMode] = useState(false);
  const [draftGraph, setDraftGraph] =
    useState<CausalArtifactPayload>(sourceGraph);
  const [persistenceDirty, setPersistenceDirty] = useState(false);
  const [draftNodeLabel, setDraftNodeLabel] = useState("");
  const [draftNodeKind, setDraftNodeKind] =
    useState<CausalNodeKind>("confounder");
  const [draftEdgeSource, setDraftEdgeSource] = useState("policy");
  const [draftEdgeTarget, setDraftEdgeTarget] = useState("outcome");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);

  useEffect(() => {
    setDraftGraph(sourceGraph);
    setPersistenceDirty(false);
    setDraftEdgeSource(sourceGraph.nodes[0]?.id ?? "");
    setDraftEdgeTarget(
      sourceGraph.nodes[1]?.id ?? sourceGraph.nodes[0]?.id ?? "",
    );
  }, [sourceGraph]);

  useEffect(() => {
    if (runDetailsQuery.isLoading) {
      return;
    }
    if (!scope) {
      return;
    }
    if (graph) {
      removeStoredCausalDraft(scope, runId);
      return;
    }
    if (persistenceDirty) {
      writeStoredCausalDraft(scope, runId, draftGraph);
    }
  }, [
    draftGraph,
    graph,
    persistenceDirty,
    runDetailsQuery.isLoading,
    runId,
    scope,
  ]);

  useEffect(() => {
    if (!draftGraph) {
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
  }, [draftGraph]);

  if (runDetailsQuery.isLoading) {
    return <PanelSkeleton rows={6} />;
  }

  if (!draftGraph || draftGraph.nodes.length === 0) {
    return <EmptyState title={t("causal.title")} body={t("causal.empty")} />;
  }

  const selectedNode = selectedNodeId
    ? (draftGraph.nodes.find((node) => node.id === selectedNodeId) ?? null)
    : null;
  const selectedEdge = selectedEdgeId
    ? (draftGraph.edges.find((edge) => edge.id === selectedEdgeId) ?? null)
    : null;
  const selectedPath = selectedPathId
    ? (draftGraph.paths.find((path) => path.id === selectedPathId) ?? null)
    : null;
  const highlightedEdges = adversarialMode
    ? draftGraph.edges
        .filter((edge) => edge.status.label !== "identified")
        .map((edge) => edge.id)
    : (selectedPath?.edgeIds ?? []);

  return (
    <div className="space-y-6">
      <Card className="space-y-4" data-testid="causal-atlas-editor">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{t("phase32.causal.eyebrow")}</p>
            <h3>{t("phase32.causal.title")}</h3>
            <p className="topbar-subtitle mt-2">{t("phase32.causal.body")}</p>
          </div>
          <Badge kind="warn">{t("phase32.causal.draft")}</Badge>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_12rem_auto]">
            <div>
              <Label htmlFor="causal-node-label">
                {t("phase32.causal.nodeLabel")}
              </Label>
              <Input
                id="causal-node-label"
                value={draftNodeLabel}
                onChange={(event) => setDraftNodeLabel(event.target.value)}
                placeholder={t("phase32.causal.nodePlaceholder")}
              />
            </div>
            <div>
              <Label htmlFor="causal-node-kind">
                {t("phase32.causal.nodeKind")}
              </Label>
              <Select
                id="causal-node-kind"
                value={draftNodeKind}
                onChange={(event) =>
                  setDraftNodeKind(event.target.value as CausalNodeKind)
                }
              >
                {CAUSAL_NODE_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                type="button"
                disabled={!draftNodeLabel.trim()}
                onClick={() => {
                  const existingIds = new Set(
                    draftGraph.nodes.map((node) => node.id),
                  );
                  const id = nextDraftId(draftNodeLabel, existingIds);
                  const nodes: CausalNodeData[] = [
                    ...draftGraph.nodes,
                    {
                      dataAvailable: false,
                      id,
                      kind: draftNodeKind,
                      label: draftNodeLabel.trim(),
                    },
                  ];
                  setDraftGraph({
                    ...draftGraph,
                    nodes,
                    paths: deriveCausalPaths(nodes, draftGraph.edges),
                  });
                  setPersistenceDirty(true);
                  setDraftNodeLabel("");
                }}
                variant="primary"
              >
                {t("phase32.causal.addNode")}
              </Button>
            </div>
          </div>

          <Button
            type="button"
            aria-pressed={adversarialMode}
            onClick={() => setAdversarialMode((value) => !value)}
            variant={adversarialMode ? "danger" : "ghost"}
          >
            {t("phase32.causal.adversarial")}
          </Button>
        </div>

        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <Select
            value={draftEdgeSource}
            onChange={(event) => setDraftEdgeSource(event.target.value)}
            aria-label={t("phase32.causal.edgeSource")}
          >
            {draftGraph.nodes.map((node) => (
              <option key={node.id} value={node.id}>
                {node.label}
              </option>
            ))}
          </Select>
          <Select
            value={draftEdgeTarget}
            onChange={(event) => setDraftEdgeTarget(event.target.value)}
            aria-label={t("phase32.causal.edgeTarget")}
          >
            {draftGraph.nodes.map((node) => (
              <option key={node.id} value={node.id}>
                {node.label}
              </option>
            ))}
          </Select>
          <Button
            type="button"
            disabled={!draftEdgeSource || draftEdgeSource === draftEdgeTarget}
            onClick={() => {
              const edgeId = `${draftEdgeSource}-${draftEdgeTarget}`;
              if (draftGraph.edges.some((edge) => edge.id === edgeId)) {
                return;
              }
              const edges: CausalEdgeData[] = [
                ...draftGraph.edges,
                {
                  id: edgeId,
                  source: draftEdgeSource,
                  status:
                    createCausalDraftIdentificationDisplay("unidentified"),
                  target: draftEdgeTarget,
                },
              ];
              setDraftGraph({
                ...draftGraph,
                edges,
                paths: deriveCausalPaths(draftGraph.nodes, edges),
              });
              setPersistenceDirty(true);
            }}
          >
            {t("phase32.causal.addEdge")}
          </Button>
        </div>
      </Card>

      {/* Main graph canvas */}
      <div className="relative min-h-[400px]">
        <CausalGraphCanvas
          nodes={draftGraph.nodes}
          edges={draftGraph.edges}
          adjustmentSet={draftGraph.adjustmentSet}
          highlightedPath={highlightedEdges}
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
            edges={draftGraph.edges}
            className="absolute top-4 right-4 z-10 w-64"
          />
        )}
        {overlay === "transport" && (
          <TransportOverlay
            edges={draftGraph.edges}
            className="absolute top-4 right-4 z-10 w-72"
          />
        )}
        {overlay === "adjustment_set" && (
          <AdjustmentSetHighlight
            nodes={draftGraph.nodes}
            adjustmentSet={draftGraph.adjustmentSet}
            className="absolute top-4 right-4 z-10 w-72"
          />
        )}
      </div>

      {/* Detail panels */}
      <div className="grid gap-4 lg:grid-cols-2">
        {selectedNode && (
          <NodeDetailPanel
            node={selectedNode}
            edges={draftGraph.edges}
            onClose={() => setSelectedNodeId(null)}
          />
        )}
        {selectedEdge && (
          <EdgeDetailPanel
            edge={selectedEdge}
            onClose={() => setSelectedEdgeId(null)}
          />
        )}
      </div>

      {/* Path analysis */}
      {draftGraph.paths.length > 0 && (
        <PathAnalysisPanel
          nodes={draftGraph.nodes}
          edges={draftGraph.edges}
          paths={draftGraph.paths}
          selectedPathId={selectedPathId}
          onPathSelect={setSelectedPathId}
          onClose={() => setSelectedPathId(null)}
        />
      )}

      {/* Method-specific visualization */}
      <MethodVisualization
        methodology={draftGraph.methodology}
        data={draftGraph.methodData}
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
  const authz = useAuthz();
  const scope = useMemo<AuthorityLocalScope | null>(
    () =>
      authz.status === "ready" &&
      authz.user?.tenant_id &&
      authz.user.user_id
        ? {
            tenantId: authz.user.tenant_id,
            userId: authz.user.user_id,
          }
        : null,
    [authz.status, authz.user?.tenant_id, authz.user?.user_id],
  );

  if (!runId) return null;

  const persistenceBinding = JSON.stringify(
    scope
      ? ["scoped", scope.tenantId, scope.userId, runId]
      : ["unscoped", runId],
  );

  return (
    <FeatureAsyncBoundary
      body={t("causal.subtitle")}
      feature="runs.causal"
      loading={<PanelSkeleton rows={6} />}
      resetKeys={[runId]}
      title={t("causal.title")}
    >
      <CausalTabContent
        key={persistenceBinding}
        runId={runId}
        scope={scope}
      />
    </FeatureAsyncBoundary>
  );
}
