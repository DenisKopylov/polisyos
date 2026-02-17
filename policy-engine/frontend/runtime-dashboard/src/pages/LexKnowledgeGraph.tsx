import { useState } from "react";

import { useLexGraphStats } from "../api/hooks/useLexGraphStats";
import { useLexPipelineStatus } from "../api/hooks/useLexPipelineStatus";
import { useLexSearch, type LexSearchRequest } from "../api/hooks/useLexSearch";
import { useLexTrigger, type LexTriggerRequest } from "../api/hooks/useLexTrigger";
import ApiErrorAlert from "../components/shared/ApiErrorAlert";
import { Card } from "../components/ui/card";
import { cn } from "../lib/utils";

const DEFAULT_CARDS = "data/data_lex/edrnpa_cards_2026-02-08.xml";
const DEFAULT_TEXTS = "data/data_lex/edrnpa_texts_2026-02-08.xml";
const DEFAULT_OUTPUT = "data/lex_knowledge";

export default function LexKnowledgeGraph() {
  // --- Pipeline form state ---
  const [cardsPath, setCardsPath] = useState(DEFAULT_CARDS);
  const [textsPath, setTextsPath] = useState(DEFAULT_TEXTS);
  const [outputDir, setOutputDir] = useState(DEFAULT_OUTPUT);
  const [llmModel, setLlmModel] = useState("qwen/qwen3-235b-a22b-instruct-2507-fp8");
  const [statusFilter, setStatusFilter] = useState("Чинний");
  const [resume, setResume] = useState(false);
  const [stages, setStages] = useState({
    parse: true,
    structure: true,
    spo: true,
    graph: true,
    embed: true,
  });

  // --- Active pipeline tracking ---
  const [activePipelineId, setActivePipelineId] = useState<string | null>(null);

  // --- Search state ---
  const [searchQuery, setSearchQuery] = useState("");

  // --- Hooks ---
  const triggerMutation = useLexTrigger();
  const statusQuery = useLexPipelineStatus(activePipelineId);
  const statsQuery = useLexGraphStats(outputDir);
  const searchMutation = useLexSearch();

  function toggleStage(stage: keyof typeof stages) {
    setStages((prev) => ({ ...prev, [stage]: !prev[stage] }));
  }

  function handleTrigger() {
    const body: LexTriggerRequest = {
      cards_path: cardsPath,
      texts_path: textsPath,
      output_dir: outputDir,
      stages,
      llm_model: llmModel,
      resume,
      status_filter: statusFilter.trim() ? statusFilter.split(",").map((s) => s.trim()) : null,
    };
    triggerMutation.mutate(body, {
      onSuccess: (data) => {
        if (data.status === "accepted") {
          setActivePipelineId(data.pipeline_id);
        }
      },
    });
  }

  function handleSearch() {
    if (!searchQuery.trim()) return;
    const body: LexSearchRequest = {
      query: searchQuery.trim(),
      top_k: 20,
      output_dir: outputDir,
    };
    searchMutation.mutate(body);
  }

  const pipelineState = statusQuery.data?.state;
  const isRunning = pipelineState === "running" || pipelineState === "pending";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Lex Knowledge Graph</h2>
        <p className="text-sm text-muted">
          Build and search the legal knowledge graph from Ukrainian НПА (ЄДРНПА).
        </p>
      </div>

      {/* ---- Pipeline Control ---- */}
      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Pipeline Control
        </h3>

        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-muted">Cards XML Path</label>
              <input
                type="text"
                value={cardsPath}
                onChange={(e) => setCardsPath(e.target.value)}
                className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-mono"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Texts XML Path</label>
              <input
                type="text"
                value={textsPath}
                onChange={(e) => setTextsPath(e.target.value)}
                className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-mono"
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs text-muted">Output Directory</label>
              <input
                type="text"
                value={outputDir}
                onChange={(e) => setOutputDir(e.target.value)}
                className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-mono"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">LLM Model</label>
              <input
                type="text"
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-mono"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Status Filter</label>
              <input
                type="text"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                placeholder="Чинний, ..."
                className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
              />
            </div>
          </div>

          {/* Stage toggles */}
          <div>
            <label className="mb-2 block text-xs text-muted">Stages</label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(stages) as (keyof typeof stages)[]).map((stage) => (
                <label
                  key={stage}
                  className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs hover:bg-text/5"
                >
                  <input
                    type="checkbox"
                    checked={stages[stage]}
                    onChange={() => toggleStage(stage)}
                    className="accent-accent"
                  />
                  {stage}
                </label>
              ))}
              <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs hover:bg-text/5">
                <input
                  type="checkbox"
                  checked={resume}
                  onChange={() => setResume(!resume)}
                  className="accent-accent"
                />
                resume
              </label>
            </div>
          </div>

          <button
            type="button"
            disabled={triggerMutation.isPending || isRunning}
            onClick={handleTrigger}
            className="rounded-xl bg-accent px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
          >
            {triggerMutation.isPending ? "Launching..." : isRunning ? "Pipeline Running..." : "Launch Pipeline"}
          </button>

          {triggerMutation.error && <ApiErrorAlert error={triggerMutation.error} />}

          {triggerMutation.data && triggerMutation.data.status === "accepted" && (
            <p className="text-sm text-green-500">{triggerMutation.data.message}</p>
          )}
          {triggerMutation.data && triggerMutation.data.status === "rejected" && (
            <p className="text-sm text-red-500">{triggerMutation.data.message}</p>
          )}
        </div>
      </Card>

      {/* ---- Pipeline Status (shown when active) ---- */}
      {activePipelineId && (
        <Card>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
            Pipeline Status
          </h3>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-muted">{activePipelineId}</span>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
                  pipelineState === "completed" && "bg-green-500/10 text-green-500",
                  pipelineState === "running" && "bg-blue-500/10 text-blue-500",
                  pipelineState === "pending" && "bg-yellow-500/10 text-yellow-500",
                  pipelineState === "failed" && "bg-red-500/10 text-red-500",
                )}
              >
                {pipelineState ?? "unknown"}
              </span>
            </div>

            {statusQuery.data?.error_message && (
              <p className="text-xs text-red-500">{statusQuery.data.error_message}</p>
            )}

            {statusQuery.data?.progress_summary &&
              Object.keys(statusQuery.data.progress_summary).length > 0 && (
                <div className="mt-2">
                  <p className="mb-1 text-xs text-muted">Progress:</p>
                  <div className="flex flex-wrap gap-3">
                    {Object.entries(statusQuery.data.progress_summary).map(([stage, count]) => (
                      <span key={stage} className="text-xs">
                        <span className="text-muted">{stage}:</span>{" "}
                        <span className="font-semibold">{count.toLocaleString()}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
          </div>
        </Card>
      )}

      {/* ---- Graph Statistics ---- */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Graph Statistics
          </h3>
          <button
            type="button"
            onClick={() => statsQuery.refetch()}
            disabled={statsQuery.isFetching}
            className="rounded-lg border border-line px-3 py-1 text-xs text-muted transition hover:bg-text/5 disabled:opacity-50"
          >
            {statsQuery.isFetching ? "Loading..." : "Refresh"}
          </button>
        </div>

        {statsQuery.error && <ApiErrorAlert error={statsQuery.error} />}

        {statsQuery.data && !statsQuery.data.db_exists && (
          <p className="text-sm text-muted">
            No knowledge graph found at <span className="font-mono">{outputDir}</span>. Run the
            pipeline first.
          </p>
        )}

        {statsQuery.data && statsQuery.data.db_exists && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-xl border border-line bg-surface p-3 text-center">
                <p className="text-2xl font-bold">{statsQuery.data.total_entities.toLocaleString()}</p>
                <p className="text-xs text-muted">Entities</p>
              </div>
              <div className="rounded-xl border border-line bg-surface p-3 text-center">
                <p className="text-2xl font-bold">{statsQuery.data.total_facts.toLocaleString()}</p>
                <p className="text-xs text-muted">Facts</p>
              </div>
              <div className="rounded-xl border border-line bg-surface p-3 text-center">
                <p className="text-2xl font-bold">
                  {statsQuery.data.total_provisions.toLocaleString()}
                </p>
                <p className="text-xs text-muted">Provisions</p>
              </div>
            </div>

            {statsQuery.data.top_predicates.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold text-muted">Top Predicates</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-line text-muted">
                        <th className="px-2 py-1">Predicate</th>
                        <th className="px-2 py-1 text-right">Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {statsQuery.data.top_predicates.map((p) => (
                        <tr key={p.predicate} className="border-b border-line/50">
                          <td className="px-2 py-1 font-mono">{p.predicate}</td>
                          <td className="px-2 py-1 text-right">
                            {(p.count as number).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {statsQuery.data.top_entity_types.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold text-muted">Entity Types</p>
                <div className="flex flex-wrap gap-2">
                  {statsQuery.data.top_entity_types.map((t) => (
                    <span
                      key={t.entity_type}
                      className="rounded-lg bg-text/5 px-2 py-1 font-mono text-[10px]"
                    >
                      {t.entity_type}: {(t.count as number).toLocaleString()}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* ---- Knowledge Search ---- */}
      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Knowledge Search
        </h3>

        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search facts (e.g. бюджетний дефіцит, liability, tax rate...)"
              className="flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm"
            />
            <button
              type="button"
              disabled={searchMutation.isPending || !searchQuery.trim()}
              onClick={handleSearch}
              className="rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
            >
              {searchMutation.isPending ? "Searching..." : "Search"}
            </button>
          </div>

          {searchMutation.error && <ApiErrorAlert error={searchMutation.error} />}

          {searchMutation.data && searchMutation.data.results.length === 0 && (
            <p className="text-sm text-muted">No results found for &ldquo;{searchMutation.data.query}&rdquo;</p>
          )}

          {searchMutation.data && searchMutation.data.results.length > 0 && (
            <div>
              <p className="mb-2 text-xs text-muted">
                {searchMutation.data.total} result(s) for &ldquo;{searchMutation.data.query}&rdquo;
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line text-muted">
                      <th className="px-2 py-1">Subject</th>
                      <th className="px-2 py-1">Predicate</th>
                      <th className="px-2 py-1">Object</th>
                      <th className="px-2 py-1">Fact</th>
                      <th className="px-2 py-1">Type</th>
                      <th className="px-2 py-1">Document</th>
                      <th className="px-2 py-1 text-right">Conf.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {searchMutation.data.results.map((r) => (
                      <tr key={r.fact_id} className="border-b border-line/50">
                        <td className="px-2 py-1 font-mono text-[10px]">{r.subject_name}</td>
                        <td className="px-2 py-1 font-mono text-[10px] text-accent">
                          {r.predicate}
                        </td>
                        <td className="px-2 py-1 font-mono text-[10px]">{r.object_name}</td>
                        <td className="max-w-xs truncate px-2 py-1">{r.fact_text}</td>
                        <td className="px-2 py-1">
                          <span
                            className={cn(
                              "rounded px-1.5 py-0.5 text-[10px] font-semibold",
                              r.norm_type === "obligation" && "bg-blue-500/10 text-blue-500",
                              r.norm_type === "prohibition" && "bg-red-500/10 text-red-500",
                              r.norm_type === "permission" && "bg-green-500/10 text-green-500",
                              r.norm_type === "definition" && "bg-purple-500/10 text-purple-500",
                            )}
                          >
                            {r.norm_type}
                          </span>
                        </td>
                        <td className="max-w-[200px] truncate px-2 py-1 text-muted">
                          {r.doc_name}
                          {r.provision_citation && (
                            <span className="ml-1 text-[10px]">({r.provision_citation})</span>
                          )}
                        </td>
                        <td className="px-2 py-1 text-right">{r.confidence.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
