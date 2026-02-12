import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { useArtifactContent } from "../api/hooks/useArtifactContent";
import { useArtifactLineage } from "../api/hooks/useArtifactLineage";
import { useArtifactManifest } from "../api/hooks/useArtifactManifest";
import { useArtifactSchema } from "../api/hooks/useArtifactSchema";
import ApiErrorAlert from "../components/shared/ApiErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import JsonPreview from "../components/shared/JsonPreview";
import LineageGraph from "../components/shared/LineageGraph";
import { Card } from "../components/ui/card";
import { formatDate } from "../lib/utils";

const TrinityCard = lazy(() => import("../components/trinity/TrinityCard"));
const SimulationResultsViewer = lazy(() => import("../components/simulation/SimulationResultsViewer"));
const DecisionCardView = lazy(() => import("../components/decision/DecisionCardView"));

type ArtifactTab = "content" | "schema" | "lineage";
const ARTIFACT_TABS: ArtifactTab[] = ["content", "schema", "lineage"];
const PREVIEW_LIMITS = [64 * 1024, 256 * 1024, 1024 * 1024, 2_000_000] as const;

const SIMULATION_KINDS = new Set<string>([
  "scientist.decision_packet",
  "foundry.metrics",
  "foundry.simulation_result",
  "scientist.simulation_results",
  "foundry.calibration_report",
  "ir.distributional_report",
  "ir.uncertainty_envelope",
]);

function isSimulationKind(kind: string): boolean {
  return SIMULATION_KINDS.has(kind) || kind.includes("simulation") || kind.includes("calibration");
}

function nextPreviewLimit(current: number): number | null {
  for (const limit of PREVIEW_LIMITS) {
    if (limit > current) {
      return limit;
    }
  }
  return null;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function renderContent(kind: string, preview: unknown) {
  if (kind === "ir.trinity_bundle") {
    return (
      <Suspense fallback={<p className="text-sm text-muted">Loading Trinity viewer...</p>}>
        <TrinityCard payload={preview} />
      </Suspense>
    );
  }

  if (kind === "scientist.decision_card" || kind === "scientist.decision_packet") {
    return (
      <Suspense fallback={<p className="text-sm text-muted">Loading decision card viewer...</p>}>
        <DecisionCardView payload={preview} artifactKind={kind} />
      </Suspense>
    );
  }

  if (isSimulationKind(kind)) {
    return (
      <Suspense fallback={<p className="text-sm text-muted">Loading simulation viewer...</p>}>
        <SimulationResultsViewer artifactKind={kind} preview={preview} />
      </Suspense>
    );
  }

  return <JsonPreview data={preview} />;
}

export default function ArtifactInspector() {
  const { artifactId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [previewLimit, setPreviewLimit] = useState<number>(PREVIEW_LIMITS[0]);

  const requestedTab = searchParams.get("tab") as ArtifactTab | null;
  const activeTab: ArtifactTab =
    requestedTab && ARTIFACT_TABS.includes(requestedTab) ? requestedTab : "content";

  useEffect(() => {
    setPreviewLimit(PREVIEW_LIMITS[0]);
  }, [artifactId]);

  const manifestQuery = useArtifactManifest(artifactId);
  const contentQuery = useArtifactContent(artifactId, {
    enabled: activeTab === "content",
    maxBytes: previewLimit,
  });
  const schemaQuery = useArtifactSchema(artifactId, activeTab === "schema");
  const lineageQuery = useArtifactLineage(artifactId, activeTab === "lineage");

  const manifest = manifestQuery.data?.artifact;

  const manifestSummary = useMemo(
    () => ({
      kind: manifest?.kind ?? "-",
      created: formatDate(manifest?.created_at),
      producer: manifest?.producer_component ?? "-",
      size: manifest ? formatBytes(manifest.byte_size) : "-",
      schema:
        manifest?.schema_name && manifest?.schema_version
          ? `${manifest.schema_name}@${manifest.schema_version}`
          : "-",
    }),
    [manifest],
  );

  function selectTab(tab: ArtifactTab) {
    const next = new URLSearchParams(searchParams);
    next.set("tab", tab);
    setSearchParams(next);
  }

  if (!artifactId) {
    return <Card>Artifact ID is required.</Card>;
  }

  const content = contentQuery.data?.artifact;
  const canLoadMore = content ? Boolean(content.truncated && nextPreviewLimit(previewLimit) !== null) : false;

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="mb-2 text-xl font-semibold">Artifact Inspector</h2>
        <p className="mb-3 font-mono text-xs">{artifactId}</p>

        {manifestQuery.isLoading ? <p className="text-sm text-muted">Loading manifest...</p> : null}
        {manifestQuery.isError ? (
          <ApiErrorAlert title="Unable to load artifact manifest" error={manifestQuery.error} />
        ) : null}

        {manifest ? (
          <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2 lg:grid-cols-5">
            <div>
              <dt className="text-muted">Kind</dt>
              <dd>{manifestSummary.kind}</dd>
            </div>
            <div>
              <dt className="text-muted">Created</dt>
              <dd>{manifestSummary.created}</dd>
            </div>
            <div>
              <dt className="text-muted">Size</dt>
              <dd>{manifestSummary.size}</dd>
            </div>
            <div>
              <dt className="text-muted">Producer</dt>
              <dd>{manifestSummary.producer}</dd>
            </div>
            <div>
              <dt className="text-muted">Schema</dt>
              <dd className="font-mono text-xs">{manifestSummary.schema}</dd>
            </div>
          </dl>
        ) : null}
      </Card>

      <Card>
        <div className="mb-4 flex gap-2">
          {ARTIFACT_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => selectTab(tab)}
              className={
                activeTab === tab
                  ? "rounded-lg border border-text/20 bg-text px-3 py-2 text-sm font-semibold text-white"
                  : "rounded-lg border border-line bg-panel px-3 py-2 text-sm font-semibold"
              }
            >
              {tab}
            </button>
          ))}
        </div>

        {activeTab === "content" ? (
          <div className="space-y-3">
            {contentQuery.isLoading ? <p className="text-sm text-muted">Loading content preview...</p> : null}
            {contentQuery.isError ? (
              <ApiErrorAlert title="Unable to load artifact content" error={contentQuery.error} />
            ) : null}

            {!contentQuery.isLoading && !contentQuery.isError && content ? (
              <>
                <div className="grid gap-2 md:grid-cols-5">
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Mode</p>
                    <p className="font-semibold">{content.mode}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Media type</p>
                    <p className="font-semibold">{content.media_type}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Artifact size</p>
                    <p className="font-semibold">{formatBytes(content.size_bytes)}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Preview limit</p>
                    <p className="font-semibold">{formatBytes(content.max_bytes)}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Truncated</p>
                    <p className="font-semibold">{content.truncated ? "yes" : "no"}</p>
                  </div>
                </div>

                {content.truncated ? (
                  <div className="flex flex-wrap items-center gap-2 rounded-xl border border-warning/30 bg-warning/5 p-3 text-sm text-warning">
                    <span>Preview is truncated.</span>
                    {canLoadMore ? (
                      <button
                        type="button"
                        onClick={() => {
                          const nextLimit = nextPreviewLimit(previewLimit);
                          if (nextLimit !== null) {
                            setPreviewLimit(nextLimit);
                          }
                        }}
                        className="rounded-lg border border-warning/30 bg-panel px-2 py-1 text-xs font-semibold text-text"
                      >
                        Load larger preview
                      </button>
                    ) : (
                      <span>Reached max preview limit.</span>
                    )}
                  </div>
                ) : null}

                {renderContent(content.kind, content.preview)}
              </>
            ) : null}
          </div>
        ) : null}

        {activeTab === "schema" ? (
          <div className="space-y-3">
            {schemaQuery.isLoading ? <p className="text-sm text-muted">Loading schema metadata...</p> : null}
            {schemaQuery.isError ? (
              <ApiErrorAlert title="Unable to load schema" error={schemaQuery.error} />
            ) : null}

            {!schemaQuery.isLoading && !schemaQuery.isError && schemaQuery.data ? (
              <>
                <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
                  <div>
                    <dt className="text-muted">Schema name</dt>
                    <dd>{schemaQuery.data.schema.schema_name ?? "-"}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">Schema version</dt>
                    <dd>{schemaQuery.data.schema.schema_version ?? "-"}</dd>
                  </div>
                </dl>

                {(schemaQuery.data.schema.top_level_keys ?? []).length ? (
                  <div className="rounded-xl border border-line p-3">
                    <p className="mb-2 text-xs font-semibold uppercase text-muted">Top-level keys</p>
                    <div className="flex flex-wrap gap-2">
                      {(schemaQuery.data.schema.top_level_keys ?? []).map((key) => (
                        <span
                          key={key}
                          className="rounded-lg border border-line bg-panel px-2 py-1 font-mono text-xs"
                        >
                          {key}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <EmptyState
                    title="No schema keys"
                    body="Schema endpoint returned no top-level keys for this artifact."
                  />
                )}
              </>
            ) : null}
          </div>
        ) : null}

        {activeTab === "lineage" ? (
          <div className="space-y-3">
            {lineageQuery.isLoading ? <p className="text-sm text-muted">Loading artifact lineage...</p> : null}
            {lineageQuery.isError ? (
              <ApiErrorAlert title="Unable to load artifact lineage" error={lineageQuery.error} />
            ) : null}

            {!lineageQuery.isLoading && !lineageQuery.isError && lineageQuery.data ? (
              <>
                <div className="grid gap-2 md:grid-cols-4">
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Nodes</p>
                    <p className="font-semibold">{lineageQuery.data.lineage.total_nodes}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Edges</p>
                    <p className="font-semibold">{lineageQuery.data.lineage.total_edges}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Complete</p>
                    <p className="font-semibold">{lineageQuery.data.lineage.is_complete ? "yes" : "no"}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Size</p>
                    <p className="font-semibold">{formatBytes(lineageQuery.data.lineage.total_size_bytes)}</p>
                  </div>
                </div>

                <LineageGraph
                  nodes={lineageQuery.data.lineage.nodes}
                  edges={lineageQuery.data.lineage.edges}
                  rootArtifactIds={lineageQuery.data.lineage.root_artifact_ids}
                />

                {lineageQuery.data.lineage.missing_artifact_ids.length > 0 ? (
                  <p className="text-sm text-warning">
                    Missing artifacts: {lineageQuery.data.lineage.missing_artifact_ids.join(", ")}
                  </p>
                ) : null}

                {lineageQuery.data.lineage.corrupted_artifact_ids.length > 0 ? (
                  <p className="text-sm text-danger">
                    Corrupted artifacts: {lineageQuery.data.lineage.corrupted_artifact_ids.join(", ")}
                  </p>
                ) : null}
              </>
            ) : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
