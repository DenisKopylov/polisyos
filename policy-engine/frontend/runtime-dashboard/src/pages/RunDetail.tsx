import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { useArtifactContent } from "../api/hooks/useArtifactContent";
import { useGovernanceDebug } from "../api/hooks/useGovernanceDebug";
import { useNodeDebug } from "../api/hooks/useNodeDebug";
import { useRunAgents } from "../api/hooks/useRunAgents";
import { useRunDetails } from "../api/hooks/useRunDetails";
import { useRunErrors } from "../api/hooks/useRunErrors";
import { useRunLineage } from "../api/hooks/useRunLineage";
import { useRunNodes } from "../api/hooks/useRunNodes";
import { useRunTimeline } from "../api/hooks/useRunTimeline";
import { useRunWorkflow } from "../api/hooks/useRunWorkflow";
import AgentPipelinePanel from "../components/agents/AgentPipelinePanel";
import ErrorsPanel from "../components/debug/ErrorsPanel";
import NodeDebugPanel from "../components/debug/NodeDebugPanel";
import GovernanceReport from "../components/governance/GovernanceReport";
import ApiErrorAlert from "../components/shared/ApiErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import LineageGraph from "../components/shared/LineageGraph";
import StatusBadge from "../components/shared/StatusBadge";
import { Card } from "../components/ui/card";
import WorkflowDagPanel from "../components/workflow/WorkflowDagPanel";
import { asRecord, asString } from "../lib/parsing";
import { formatBytes, formatDate, formatDuration } from "../lib/utils";

const DecisionCardView = lazy(() => import("../components/decision/DecisionCardView"));

type RunTab =
  | "timeline"
  | "nodes"
  | "lineage"
  | "agents"
  | "models"
  | "workflow"
  | "governance"
  | "debug"
  | "decision";
const RUN_TABS: RunTab[] = ["timeline", "nodes", "lineage", "agents", "models", "workflow", "governance", "debug", "decision"];

const DECISION_PREVIEW_LIMITS = [256 * 1024, 1024 * 1024, 2_000_000] as const;

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

function eventKind(eventName: string, errorCount?: number, warningCount?: number) {
  if ((errorCount ?? 0) > 0 || /fail|error/i.test(eventName)) {
    return "fail" as const;
  }
  if ((warningCount ?? 0) > 0 || /warn/i.test(eventName)) {
    return "warn" as const;
  }
  if (/ok|success|done/i.test(eventName)) {
    return "ok" as const;
  }
  return "unknown" as const;
}

function decisionArtifactRank(kind: string | null): number {
  if (!kind) {
    return 30;
  }
  const normalized = kind.toLowerCase();
  if (normalized === "scientist.decision_card") {
    return 0;
  }
  if (normalized === "scientist.decision_packet") {
    return 1;
  }
  if (normalized.includes("decision")) {
    return 5;
  }
  if (normalized.includes("governance")) {
    return 20;
  }
  return 100;
}

function nextPreviewLimit(current: number): number | null {
  for (const candidate of DECISION_PREVIEW_LIMITS) {
    if (candidate > current) {
      return candidate;
    }
  }
  return null;
}

export default function RunDetail() {
  const { runId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const requestedTab = searchParams.get("tab") as RunTab | null;
  const activeTab: RunTab = requestedTab && RUN_TABS.includes(requestedTab) ? requestedTab : "timeline";

  const [selectedDebugAlias, setSelectedDebugAlias] = useState<string | null>(null);
  const [selectedDecisionArtifactId, setSelectedDecisionArtifactId] = useState<string | null>(null);
  const [decisionPreviewLimit, setDecisionPreviewLimit] = useState<number>(DECISION_PREVIEW_LIMITS[0]);

  const runQuery = useRunDetails(runId);
  const timelineQuery = useRunTimeline(runId, activeTab === "timeline");
  const nodesQuery = useRunNodes(runId, activeTab === "nodes" || activeTab === "debug");
  const lineageQuery = useRunLineage(runId, activeTab === "lineage");
  const agentsQuery = useRunAgents(runId, activeTab === "agents" || activeTab === "models");
  const workflowQuery = useRunWorkflow(runId, activeTab === "workflow");
  const governanceQuery = useGovernanceDebug(runId, activeTab === "governance");
  const errorsQuery = useRunErrors(runId, activeTab === "governance" || activeTab === "debug");

  useEffect(() => {
    setDecisionPreviewLimit(DECISION_PREVIEW_LIMITS[0]);
  }, [runId]);

  useEffect(() => {
    if (!nodesQuery.data?.nodes.length) {
      setSelectedDebugAlias(null);
      return;
    }
    setSelectedDebugAlias((current) => {
      if (current && nodesQuery.data?.nodes.some((node) => node.alias === current)) {
        return current;
      }
      return nodesQuery.data?.nodes[0]?.alias ?? null;
    });
  }, [nodesQuery.data?.nodes]);

  const nodeDebugQuery = useNodeDebug(runId, selectedDebugAlias, activeTab === "debug");

  if (!runId) {
    return <Card>Run ID is required.</Card>;
  }

  if (runQuery.isLoading) {
    return <Card>Loading run details...</Card>;
  }

  if (runQuery.isError) {
    return <ApiErrorAlert title="Unable to load run details" error={runQuery.error} />;
  }

  const run = runQuery.data?.run;
  if (!run) {
    return <Card>Run is unavailable.</Card>;
  }

  const rootArtifacts = useMemo(() => run.root_artifacts ?? [], [run.root_artifacts]);

  const decisionCandidates = useMemo(() => {
    const sorted = [...rootArtifacts]
      .map((ref) => ({
        ...ref,
        kind: asString(ref.kind),
        rank: decisionArtifactRank(asString(ref.kind)),
      }))
      .sort((left, right) => {
        if (left.rank !== right.rank) {
          return left.rank - right.rank;
        }
        return left.artifact_id.localeCompare(right.artifact_id);
      });

    if (sorted.some((item) => item.rank <= 5)) {
      return sorted.filter((item) => item.rank <= 5);
    }
    if (sorted.some((item) => item.rank < 100)) {
      return sorted.filter((item) => item.rank < 100);
    }
    return sorted.slice(0, 5);
  }, [rootArtifacts]);

  useEffect(() => {
    setSelectedDecisionArtifactId((current) => {
      if (!decisionCandidates.length) {
        return null;
      }
      if (current && decisionCandidates.some((item) => item.artifact_id === current)) {
        return current;
      }
      return decisionCandidates[0].artifact_id;
    });
  }, [decisionCandidates]);

  const selectedDecisionArtifact = useMemo(
    () => decisionCandidates.find((item) => item.artifact_id === selectedDecisionArtifactId) ?? null,
    [decisionCandidates, selectedDecisionArtifactId],
  );

  const decisionContentQuery = useArtifactContent(selectedDecisionArtifact?.artifact_id, {
    enabled: activeTab === "decision" && Boolean(selectedDecisionArtifact),
    maxBytes: decisionPreviewLimit,
  });

  const linkedDecisionCardRef = useMemo(() => {
    const artifact = decisionContentQuery.data?.artifact;
    if (!artifact || artifact.kind !== "scientist.decision_packet") {
      return null;
    }
    const preview = asRecord(artifact.preview);
    const artifactsSection = asRecord(preview?.artifacts);
    return asString(artifactsSection?.decision_card_ref);
  }, [decisionContentQuery.data?.artifact]);

  const linkedDecisionCardQuery = useArtifactContent(linkedDecisionCardRef ?? undefined, {
    enabled: activeTab === "decision" && Boolean(linkedDecisionCardRef),
    maxBytes: decisionPreviewLimit,
  });

  const displayedDecisionArtifact = linkedDecisionCardQuery.data?.artifact ?? decisionContentQuery.data?.artifact;

  const canLoadMoreDecisionPreview =
    displayedDecisionArtifact
      ? Boolean(displayedDecisionArtifact.truncated && nextPreviewLimit(decisionPreviewLimit) !== null)
      : false;

  function selectTab(tab: RunTab) {
    const next = new URLSearchParams(searchParams);
    next.set("tab", tab);
    setSearchParams(next);
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Run {run.run_id}</h2>
          <div className="flex items-center gap-2">
            <StatusBadge label={run.status} kind={statusKind(run.status)} />
            <Link
              to={`/runs/${run.run_id}?tab=governance`}
              className="rounded-lg border border-line bg-panel px-2 py-1 text-xs font-semibold"
            >
              governance
            </Link>
            <Link
              to={`/runs/${run.run_id}?tab=agents`}
              className="rounded-lg border border-line bg-panel px-2 py-1 text-xs font-semibold"
            >
              agents
            </Link>
            <Link
              to={`/runs/${run.run_id}?tab=workflow`}
              className="rounded-lg border border-line bg-panel px-2 py-1 text-xs font-semibold"
            >
              workflow
            </Link>
            <Link
              to={`/runs/${run.run_id}?tab=decision`}
              className="rounded-lg border border-line bg-panel px-2 py-1 text-xs font-semibold"
            >
              decision
            </Link>
          </div>
        </div>

        <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
          <div>
            <dt className="text-muted">Source kind</dt>
            <dd>{run.source_kind}</dd>
          </div>
          <div>
            <dt className="text-muted">Tenant</dt>
            <dd>{run.tenant_id ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-muted">Cell</dt>
            <dd>{run.cell_id ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-muted">Started</dt>
            <dd>{formatDate(run.started_at)}</dd>
          </div>
          <div>
            <dt className="text-muted">Finished</dt>
            <dd>{formatDate(run.finished_at)}</dd>
          </div>
          <div>
            <dt className="text-muted">Duration</dt>
            <dd>{formatDuration(run.duration_ms)}</dd>
          </div>
        </dl>

        {rootArtifacts.length > 0 ? (
          <div className="mt-4 border-t border-line pt-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Root artifacts</p>
            <div className="flex flex-wrap gap-2">
              {rootArtifacts.map((artifact) => (
                <Link
                  key={artifact.artifact_id}
                  to={`/artifacts/${artifact.artifact_id}`}
                  className="rounded-lg border border-line bg-panel px-2 py-1 text-xs underline"
                >
                  <span className="font-mono">{artifact.artifact_id}</span>
                  {artifact.kind ? <span className="ml-1 text-muted">({artifact.kind})</span> : null}
                </Link>
              ))}
            </div>
          </div>
        ) : null}
      </Card>

      <Card>
        <div className="mb-4 flex flex-wrap gap-2">
          {RUN_TABS.map((tab) => (
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

        {activeTab === "timeline" ? (
          <div className="space-y-3">
            {timelineQuery.isLoading ? <p className="text-sm text-muted">Loading timeline...</p> : null}
            {timelineQuery.isError ? (
              <ApiErrorAlert title="Unable to load timeline" error={timelineQuery.error} />
            ) : null}

            {!timelineQuery.isLoading && !timelineQuery.isError ? (
              <>
                <div className="grid gap-2 md:grid-cols-4">
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Events</p>
                    <p className="font-semibold">{timelineQuery.data?.timeline.summary.total_events ?? 0}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Duration</p>
                    <p className="font-semibold">
                      {formatDuration(timelineQuery.data?.timeline.summary.duration_ms)}
                    </p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Cache hits</p>
                    <p className="font-semibold">{timelineQuery.data?.timeline.summary.cache_hits ?? 0}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Cache bypasses</p>
                    <p className="font-semibold">{timelineQuery.data?.timeline.summary.cache_bypasses ?? 0}</p>
                  </div>
                </div>

                {timelineQuery.data?.timeline.events.length ? (
                  <ol className="space-y-2">
                    {timelineQuery.data.timeline.events.map((event) => (
                      <li key={`${event.index}-${event.event}`} className="rounded-xl border border-line p-3">
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <StatusBadge
                              label={event.event}
                              kind={eventKind(event.event, event.error_count, event.warning_count)}
                            />
                            <span className="text-xs text-muted">{event.phase}</span>
                          </div>
                          <span className="text-xs text-muted">{formatDate(event.timestamp)}</span>
                        </div>
                        <p className="font-mono text-xs text-muted">index={event.index}</p>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <EmptyState title="Timeline is empty" body="No timeline events were returned for this run." />
                )}
              </>
            ) : null}
          </div>
        ) : null}

        {activeTab === "nodes" ? (
          <div className="space-y-3">
            {nodesQuery.isLoading ? <p className="text-sm text-muted">Loading nodes...</p> : null}
            {nodesQuery.isError ? <ApiErrorAlert title="Unable to load nodes" error={nodesQuery.error} /> : null}

            {!nodesQuery.isLoading && !nodesQuery.isError ? (
              nodesQuery.data?.nodes.length ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                        <th className="px-3 py-2">Alias</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Duration</th>
                        <th className="px-3 py-2">Inputs</th>
                        <th className="px-3 py-2">Outputs</th>
                      </tr>
                    </thead>
                    <tbody>
                      {nodesQuery.data.nodes.map((node) => (
                        <tr key={node.alias} className="border-b border-line/70 align-top last:border-b-0">
                          <td className="px-3 py-3">
                            <p className="font-semibold">{node.alias}</p>
                            <p className="font-mono text-xs text-muted">{node.node_id ?? "-"}</p>
                          </td>
                          <td className="px-3 py-3">
                            <StatusBadge label={node.status} kind={statusKind(node.status)} />
                            {node.error_code ? (
                              <p className="mt-1 font-mono text-xs text-danger">{node.error_code}</p>
                            ) : null}
                          </td>
                          <td className="px-3 py-3">{formatDuration(node.duration_ms)}</td>
                          <td className="px-3 py-3">
                            <div className="flex flex-col gap-1">
                              {(node.input_artifact_ids ?? []).map((artifactId) => (
                                <Link key={artifactId} to={`/artifacts/${artifactId}`} className="font-mono text-xs underline">
                                  {artifactId}
                                </Link>
                              ))}
                            </div>
                          </td>
                          <td className="px-3 py-3">
                            <div className="flex flex-col gap-1">
                              {(node.output_artifact_ids ?? []).map((artifactId) => (
                                <Link key={artifactId} to={`/artifacts/${artifactId}`} className="font-mono text-xs underline">
                                  {artifactId}
                                </Link>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState title="No nodes" body="Run nodes payload is empty for this run." />
              )
            ) : null}
          </div>
        ) : null}

        {activeTab === "lineage" ? (
          <div className="space-y-3">
            {lineageQuery.isLoading ? <p className="text-sm text-muted">Loading lineage...</p> : null}
            {lineageQuery.isError ? (
              <ApiErrorAlert title="Unable to load lineage" error={lineageQuery.error} />
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
              </>
            ) : null}
          </div>
        ) : null}

        {activeTab === "agents" || activeTab === "models" ? (
          <div className="space-y-3">
            {agentsQuery.isLoading ? <p className="text-sm text-muted">Loading agent pipeline...</p> : null}
            {agentsQuery.isError ? (
              <ApiErrorAlert title="Unable to load agent pipeline" error={agentsQuery.error} />
            ) : null}
            {!agentsQuery.isLoading && !agentsQuery.isError && agentsQuery.data ? (
              <AgentPipelinePanel payload={agentsQuery.data.pipeline} />
            ) : null}
          </div>
        ) : null}

        {activeTab === "workflow" ? (
          <div className="space-y-3">
            {workflowQuery.isLoading ? <p className="text-sm text-muted">Loading workflow graph...</p> : null}
            {workflowQuery.isError ? (
              <ApiErrorAlert title="Unable to load workflow graph" error={workflowQuery.error} />
            ) : null}
            {!workflowQuery.isLoading && !workflowQuery.isError && workflowQuery.data ? (
              <WorkflowDagPanel payload={workflowQuery.data.workflow} runId={run.run_id} />
            ) : null}
          </div>
        ) : null}

        {activeTab === "governance" ? (
          <div className="space-y-4">
            {governanceQuery.isLoading ? <p className="text-sm text-muted">Loading governance report...</p> : null}
            {governanceQuery.isError ? (
              <ApiErrorAlert title="Unable to load governance debug" error={governanceQuery.error} />
            ) : null}

            {!governanceQuery.isLoading && !governanceQuery.isError && governanceQuery.data ? (
              <GovernanceReport data={governanceQuery.data.debug} />
            ) : null}

            <div>
              <p className="mb-2 text-xs font-semibold uppercase text-muted">Errors panel</p>
              {errorsQuery.isLoading ? <p className="text-sm text-muted">Loading run errors...</p> : null}
              {errorsQuery.isError ? (
                <ApiErrorAlert title="Unable to load run errors" error={errorsQuery.error} />
              ) : null}
              {!errorsQuery.isLoading && !errorsQuery.isError && errorsQuery.data ? (
                <ErrorsPanel errors={errorsQuery.data.errors} />
              ) : null}
            </div>
          </div>
        ) : null}

        {activeTab === "debug" ? (
          <div className="space-y-4">
            {nodesQuery.isLoading ? <p className="text-sm text-muted">Loading node aliases...</p> : null}
            {nodesQuery.isError ? (
              <ApiErrorAlert title="Unable to load run nodes for debug" error={nodesQuery.error} />
            ) : null}

            {!nodesQuery.isLoading && !nodesQuery.isError ? (
              nodesQuery.data?.nodes.length ? (
                <>
                  {nodeDebugQuery.isLoading ? <p className="text-sm text-muted">Loading node debug...</p> : null}
                  {nodeDebugQuery.isError ? (
                    <ApiErrorAlert title="Unable to load node debug" error={nodeDebugQuery.error} />
                  ) : null}
                  {!nodeDebugQuery.isError ? (
                    <NodeDebugPanel
                      nodes={nodesQuery.data.nodes}
                      selectedAlias={selectedDebugAlias}
                      onSelectAlias={setSelectedDebugAlias}
                      debugData={nodeDebugQuery.data?.debug ?? null}
                    />
                  ) : null}
                </>
              ) : (
                <EmptyState title="No nodes for debug" body="Run has no node records to inspect." />
              )
            ) : null}

            <div>
              <p className="mb-2 text-xs font-semibold uppercase text-muted">Run errors</p>
              {errorsQuery.isLoading ? <p className="text-sm text-muted">Loading run errors...</p> : null}
              {errorsQuery.isError ? (
                <ApiErrorAlert title="Unable to load run errors" error={errorsQuery.error} />
              ) : null}
              {!errorsQuery.isLoading && !errorsQuery.isError && errorsQuery.data ? (
                <ErrorsPanel errors={errorsQuery.data.errors} />
              ) : null}
            </div>
          </div>
        ) : null}

        {activeTab === "decision" ? (
          <div className="space-y-3">
            {decisionCandidates.length > 0 ? (
              <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-panel p-3">
                <label htmlFor="decision-artifact-select" className="text-sm font-medium">
                  Decision artifact
                </label>
                <select
                  id="decision-artifact-select"
                  value={selectedDecisionArtifactId ?? ""}
                  onChange={(event) => setSelectedDecisionArtifactId(event.target.value)}
                  className="rounded-lg border border-line bg-panel px-2 py-1 text-sm"
                >
                  {decisionCandidates.map((artifact) => (
                    <option key={artifact.artifact_id} value={artifact.artifact_id}>
                      {artifact.kind ?? "artifact"} :: {artifact.artifact_id}
                    </option>
                  ))}
                </select>
                {selectedDecisionArtifact ? (
                  <Link to={`/artifacts/${selectedDecisionArtifact.artifact_id}`} className="text-xs underline">
                    open artifact
                  </Link>
                ) : null}
              </div>
            ) : (
              <EmptyState
                title="No decision artifact candidates"
                body="Run has no root artifacts that can be used for decision rendering."
              />
            )}

            {decisionContentQuery.isLoading ? <p className="text-sm text-muted">Loading decision artifact...</p> : null}
            {decisionContentQuery.isError ? (
              <ApiErrorAlert title="Unable to load decision artifact" error={decisionContentQuery.error} />
            ) : null}

            {linkedDecisionCardRef ? (
              <div className="rounded-xl border border-line bg-canvas/30 p-2 text-xs text-muted">
                Linked decision card ref: {linkedDecisionCardRef}
              </div>
            ) : null}

            {linkedDecisionCardQuery.isLoading ? (
              <p className="text-sm text-muted">Loading linked decision card...</p>
            ) : null}
            {linkedDecisionCardQuery.isError ? (
              <ApiErrorAlert title="Unable to load linked decision card" error={linkedDecisionCardQuery.error} />
            ) : null}

            {displayedDecisionArtifact ? (
              <>
                <div className="grid gap-2 md:grid-cols-4">
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Kind</p>
                    <p className="font-semibold">{displayedDecisionArtifact.kind}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Mode</p>
                    <p className="font-semibold">{displayedDecisionArtifact.mode}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Size</p>
                    <p className="font-semibold">{formatBytes(displayedDecisionArtifact.size_bytes)}</p>
                  </div>
                  <div className="rounded-xl border border-line p-2 text-sm">
                    <p className="text-xs uppercase text-muted">Truncated</p>
                    <p className="font-semibold">{displayedDecisionArtifact.truncated ? "yes" : "no"}</p>
                  </div>
                </div>

                {displayedDecisionArtifact.truncated ? (
                  <div className="flex flex-wrap items-center gap-2 rounded-xl border border-warning/30 bg-warning/5 p-2 text-sm text-warning">
                    <span>Decision payload preview is truncated.</span>
                    {canLoadMoreDecisionPreview ? (
                      <button
                        type="button"
                        onClick={() => {
                          const nextLimit = nextPreviewLimit(decisionPreviewLimit);
                          if (nextLimit !== null) {
                            setDecisionPreviewLimit(nextLimit);
                          }
                        }}
                        className="rounded-lg border border-warning/30 bg-panel px-2 py-1 text-xs font-semibold text-text"
                      >
                        Load larger preview
                      </button>
                    ) : (
                      <span>Max preview reached.</span>
                    )}
                  </div>
                ) : null}

                <Suspense fallback={<p className="text-sm text-muted">Loading decision card view...</p>}>
                  <DecisionCardView
                    payload={displayedDecisionArtifact.preview}
                    artifactKind={displayedDecisionArtifact.kind}
                  />
                </Suspense>
              </>
            ) : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
