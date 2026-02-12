import { useState } from "react";
import { Link } from "react-router-dom";

import { useLaunchNlRun, type NaturalLanguageRunRequest } from "../api/hooks/useLaunchNlRun";
import { useLaunchRun, type WorkflowRunRequest } from "../api/hooks/useLaunchRun";
import ApiErrorAlert from "../components/shared/ApiErrorAlert";
import { Card } from "../components/ui/card";
import { cn } from "../lib/utils";

type Mode = "workflow" | "nl";

type ParamEntry = { key: string; value: string };

function RecentLaunch({ runId, status }: { runId: string; status: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2 text-sm">
      <Link to={`/runs/${runId}`} className="font-mono text-xs text-accent hover:underline">
        {runId}
      </Link>
      <span
        className={cn(
          "rounded-full px-2 py-0.5 text-xs font-medium",
          status === "accepted" ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500",
        )}
      >
        {status}
      </span>
    </div>
  );
}

export default function LaunchRun() {
  const [mode, setMode] = useState<Mode>("workflow");
  const [recentLaunches, setRecentLaunches] = useState<{ runId: string; status: string }[]>([]);

  // Workflow state
  const [dataSourceType, setDataSourceType] = useState<"snapshot" | "bindings" | "view">("snapshot");
  const [dataSourceRef, setDataSourceRef] = useState("");
  const [trinityRef, setTrinityRef] = useState("");
  const [checkpointPolicy, setCheckpointPolicy] = useState<"strict" | "lenient" | "disabled">("strict");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [policySpecRef, setPolicySpecRef] = useState("");
  const [modelSpecRef, setModelSpecRef] = useState("");
  const [customParams, setCustomParams] = useState<ParamEntry[]>([]);

  // NL state
  const [nlRequest, setNlRequest] = useState("");
  const [domainHint, setDomainHint] = useState<string>("custom");
  const [llmModel, setLlmModel] = useState<string>("");
  const [maxIterations, setMaxIterations] = useState(3);
  const [nlDataSourceRef, setNlDataSourceRef] = useState("");

  const launchRunMutation = useLaunchRun();
  const launchNlMutation = useLaunchNlRun();

  function addRecentLaunch(runId: string, status: string) {
    setRecentLaunches((prev) => [{ runId, status }, ...prev].slice(0, 5));
  }

  function handleLaunchWorkflow() {
    const dsKey =
      dataSourceType === "snapshot"
        ? "data_snapshot_ref"
        : dataSourceType === "bindings"
          ? "input_bindings_ref"
          : "data_view_request_ref";

    const params: Record<string, unknown> = {};
    for (const p of customParams) {
      if (p.key.trim()) params[p.key.trim()] = p.value;
    }

    const body: WorkflowRunRequest = {
      mode: "workflow",
      data_source: { [dsKey]: dataSourceRef } as WorkflowRunRequest["data_source"],
      checkpoint_policy: checkpointPolicy,
      params,
    };
    if (trinityRef) body.trinity_bundle_ref = trinityRef;
    if (policySpecRef) body.policy_spec_ref = policySpecRef;
    if (modelSpecRef) body.model_spec_ref = modelSpecRef;

    launchRunMutation.mutate(body, {
      onSuccess: (data) => addRecentLaunch(data.run_id, data.status),
    });
  }

  function handleLaunchNl() {
    const body: NaturalLanguageRunRequest = {
      request: nlRequest,
      domain_hint: domainHint || null,
      max_iterations: maxIterations,
      llm_model: llmModel || null,
      checkpoint_policy: checkpointPolicy,
      context: {},
    };
    if (nlDataSourceRef) {
      body.data_source = { data_snapshot_ref: nlDataSourceRef };
    }

    launchNlMutation.mutate(body, {
      onSuccess: (data) => addRecentLaunch(data.run_id, data.status),
    });
  }

  const isPending = launchRunMutation.isPending || launchNlMutation.isPending;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Launch Run</h2>
        <p className="text-sm text-muted">Start a new workflow run or submit a natural-language policy request.</p>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-2">
        {(["workflow", "nl"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={cn(
              "rounded-lg border px-4 py-2 text-sm font-medium transition",
              mode === m
                ? "border-text/20 bg-text/5 text-text"
                : "border-transparent text-muted hover:border-line hover:bg-panel",
            )}
          >
            {m === "workflow" ? "Standard Workflow" : "Natural Language"}
          </button>
        ))}
      </div>

      {/* Workflow form */}
      {mode === "workflow" && (
        <Card>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">
                Data Source
              </label>
              <div className="flex flex-col gap-2">
                {([
                  ["snapshot", "Data Snapshot Ref"],
                  ["bindings", "Input Bindings Ref"],
                  ["view", "Data View Request Ref"],
                ] as const).map(([val, label]) => (
                  <label key={val} className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="dataSourceType"
                      checked={dataSourceType === val}
                      onChange={() => setDataSourceType(val)}
                      className="accent-accent"
                    />
                    <span className="w-40 text-muted">{label}</span>
                    {dataSourceType === val && (
                      <input
                        type="text"
                        value={dataSourceRef}
                        onChange={(e) => setDataSourceRef(e.target.value)}
                        placeholder="sha256:..."
                        className="flex-1 rounded-lg border border-line bg-surface px-3 py-1.5 font-mono text-xs"
                      />
                    )}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">
                Trinity Bundle Ref (optional)
              </label>
              <input
                type="text"
                value={trinityRef}
                onChange={(e) => setTrinityRef(e.target.value)}
                placeholder="sha256:..."
                className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 font-mono text-xs"
              />
            </div>

            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-muted hover:text-text"
            >
              {showAdvanced ? "Hide" : "Show"} Advanced Options
            </button>

            {showAdvanced && (
              <div className="space-y-3 rounded-lg border border-line/50 bg-surface/50 p-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs text-muted">Policy Spec Ref</label>
                    <input
                      type="text"
                      value={policySpecRef}
                      onChange={(e) => setPolicySpecRef(e.target.value)}
                      placeholder="sha256:..."
                      className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 font-mono text-xs"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-muted">Model Spec Ref</label>
                    <input
                      type="text"
                      value={modelSpecRef}
                      onChange={(e) => setModelSpecRef(e.target.value)}
                      placeholder="sha256:..."
                      className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 font-mono text-xs"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-xs text-muted">Checkpoint Policy</label>
                  <select
                    value={checkpointPolicy}
                    onChange={(e) => setCheckpointPolicy(e.target.value as typeof checkpointPolicy)}
                    className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm"
                  >
                    <option value="strict">strict</option>
                    <option value="lenient">lenient</option>
                    <option value="disabled">disabled</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs text-muted">Custom Params</label>
                  {customParams.map((p, i) => (
                    <div key={i} className="mb-1 flex gap-2">
                      <input
                        type="text"
                        value={p.key}
                        onChange={(e) => {
                          const next = [...customParams];
                          next[i] = { ...next[i], key: e.target.value };
                          setCustomParams(next);
                        }}
                        placeholder="key"
                        className="w-40 rounded border border-line bg-surface px-2 py-1 text-xs"
                      />
                      <input
                        type="text"
                        value={p.value}
                        onChange={(e) => {
                          const next = [...customParams];
                          next[i] = { ...next[i], value: e.target.value };
                          setCustomParams(next);
                        }}
                        placeholder="value"
                        className="flex-1 rounded border border-line bg-surface px-2 py-1 text-xs"
                      />
                      <button
                        type="button"
                        onClick={() => setCustomParams(customParams.filter((_, j) => j !== i))}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => setCustomParams([...customParams, { key: "", value: "" }])}
                    className="text-xs text-accent hover:underline"
                  >
                    + Add Param
                  </button>
                </div>
              </div>
            )}

            <button
              type="button"
              disabled={isPending || !dataSourceRef.trim()}
              onClick={handleLaunchWorkflow}
              className="rounded-xl bg-accent px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
            >
              {launchRunMutation.isPending ? "Launching..." : "Launch Workflow Run"}
            </button>

            {launchRunMutation.error && <ApiErrorAlert error={launchRunMutation.error} />}
          </div>
        </Card>
      )}

      {/* NL form */}
      {mode === "nl" && (
        <Card>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">
                Describe your policy experiment
              </label>
              <textarea
                value={nlRequest}
                onChange={(e) => setNlRequest(e.target.value)}
                rows={4}
                maxLength={10000}
                placeholder="e.g., Analyze the impact of increasing minimum wage to $15/hr on small business employment in the US..."
                className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm"
              />
              <p className="mt-1 text-right text-xs text-muted">{nlRequest.length}/10000</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs text-muted">Domain Hint</label>
                <select
                  value={domainHint}
                  onChange={(e) => setDomainHint(e.target.value)}
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-sm"
                >
                  <option value="custom">Custom</option>
                  <option value="fiscal">Fiscal</option>
                  <option value="healthcare">Healthcare</option>
                  <option value="education">Education</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted">LLM Model (empty = mock agents)</label>
                <input
                  type="text"
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  placeholder="e.g., claude-sonnet-4-5-20250929"
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-sm"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs text-muted">
                Max Agent Iterations: {maxIterations}
              </label>
              <input
                type="range"
                min={1}
                max={10}
                value={maxIterations}
                onChange={(e) => setMaxIterations(Number(e.target.value))}
                className="w-full accent-accent"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-muted">Data Source Ref (optional)</label>
              <input
                type="text"
                value={nlDataSourceRef}
                onChange={(e) => setNlDataSourceRef(e.target.value)}
                placeholder="sha256:... (leave empty for agents to determine)"
                className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 font-mono text-xs"
              />
            </div>

            <button
              type="button"
              disabled={isPending || !nlRequest.trim()}
              onClick={handleLaunchNl}
              className="rounded-xl bg-accent px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
            >
              {launchNlMutation.isPending ? "Running Agent Circuit..." : "Run Agent Circuit"}
            </button>

            {launchNlMutation.error && <ApiErrorAlert error={launchNlMutation.error} />}
          </div>
        </Card>
      )}

      {/* Recent launches */}
      {recentLaunches.length > 0 && (
        <Card>
          <h3 className="mb-3 text-sm font-semibold">Recent Launches</h3>
          <div className="space-y-2">
            {recentLaunches.map((launch) => (
              <RecentLaunch key={launch.runId} runId={launch.runId} status={launch.status} />
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
