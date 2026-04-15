import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useCapabilities } from "@/api/hooks/useCapabilities";
import { useLexGraphStats } from "@/api/hooks/useLexGraphStats";
import { useLexPipelineStatus } from "@/api/hooks/useLexPipelineStatus";
import { useLexSearch, type LexSearchRequest } from "@/api/hooks/useLexSearch";
import {
  useLexTrigger,
  type LexTriggerRequest,
} from "@/api/hooks/useLexTrigger";
import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { PrefetchButton } from "@/app/routes/PrefetchButton";
import {
  buildLexHref,
  parseLexSearchParams,
  type LexSearchParams,
} from "@/features/lex/domain/searchParams";
import { useI18n } from "@/i18n/LocaleProvider";
import { DEFAULT_LEX_OUTPUT_DIR } from "@/lib/constants";
import { cn, formatNumber } from "@/lib/utils";
import {
  ApiErrorAlert,
  Button,
  Card,
  copyShareLink,
  exportCsv,
  exportJson,
} from "@/shared/ui";

const DEFAULT_CARDS = "data/data_lex/edrnpa_cards_2026-04-05.xml";
const DEFAULT_TEXTS = "data/data_lex/edrnpa_texts_2026-04-05.xml";

export default function LexKnowledgeGraph() {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const lexSearch = parseLexSearchParams(searchParams);
  const capabilitiesQuery = useCapabilities();
  useTelemetryReadyMark("lex.knowledge.page", { routeId: "lex.knowledge" });
  // --- Pipeline form state ---
  const [cardsPath, setCardsPath] = useState(DEFAULT_CARDS);
  const [textsPath, setTextsPath] = useState(DEFAULT_TEXTS);
  const [outputDir, setOutputDir] = useState(
    () => lexSearch.outputDir ?? DEFAULT_LEX_OUTPUT_DIR,
  );
  const [llmModel, setLlmModel] = useState(
    "qwen/qwen3-235b-a22b-instruct-2507-fp8",
  );
  const [statusFilter, setStatusFilter] = useState("Чинний");
  const [resume, setResume] = useState(() => lexSearch.resume ?? false);
  const [stages, setStages] = useState({
    parse: true,
    structure: true,
    spo: true,
    graph: true,
    embed: true,
  });

  // --- Active pipeline tracking ---
  const [activePipelineId, setActivePipelineId] = useState<string | null>(
    () => lexSearch.pipelineId ?? null,
  );

  // --- Search state ---
  const [searchQuery, setSearchQuery] = useState(() => lexSearch.q ?? "");

  // --- Hooks ---
  const triggerMutation = useLexTrigger();
  const statusQuery = useLexPipelineStatus(activePipelineId);
  const statsQuery = useLexGraphStats(outputDir);
  const searchMutation = useLexSearch();

  function toggleStage(stage: keyof typeof stages) {
    setStages((prev) => ({ ...prev, [stage]: !prev[stage] }));
  }

  function updateShareState(
    next: Partial<LexSearchParams>,
    options?: { replace?: boolean },
  ) {
    const href = buildLexHref({
      outputDir: next.outputDir ?? outputDir,
      pipelineId: next.pipelineId ?? activePipelineId ?? undefined,
      q: (next.q ?? searchQuery) || undefined,
      resume: (next.resume ?? resume) || undefined,
    });
    setSearchParams(new URL(href, "http://localhost").searchParams, {
      replace: options?.replace ?? false,
    });
  }

  function handleTrigger() {
    const body: LexTriggerRequest = {
      cards_path: cardsPath,
      texts_path: textsPath,
      output_dir: outputDir,
      stages,
      llm_model: llmModel,
      resume,
      status_filter: statusFilter.trim()
        ? statusFilter.split(",").map((s) => s.trim())
        : null,
    };
    triggerMutation.mutate(body, {
      onSuccess: (data) => {
        if (data.status === "accepted") {
          setActivePipelineId(data.pipeline_id);
          updateShareState({ pipelineId: data.pipeline_id });
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
    updateShareState({ outputDir, q: searchQuery.trim() });
    searchMutation.mutate(body);
  }

  const pipelineState = statusQuery.data?.state;
  const isRunning = pipelineState === "running" || pipelineState === "pending";
  const topPredicates = (statsQuery.data?.top_predicates ?? [])
    .map((entry) => ({
      predicate: typeof entry.predicate === "string" ? entry.predicate : "",
      count: typeof entry.count === "number" ? entry.count : 0,
    }))
    .filter((entry) => entry.predicate.length > 0);
  const topEntityTypes = (statsQuery.data?.top_entity_types ?? [])
    .map((entry) => ({
      entityType:
        typeof entry.entity_type === "string" ? entry.entity_type : "",
      count: typeof entry.count === "number" ? entry.count : 0,
    }))
    .filter((entry) => entry.entityType.length > 0);
  const searchResults = searchMutation.data?.results ?? [];
  const searchColumns = useMemo(
    () => [
      {
        key: "subject",
        header: t("pages.lex.columns.subject"),
        exportValue: (row: (typeof searchResults)[number]) => row.subject_name,
      },
      {
        key: "predicate",
        header: t("pages.lex.columns.predicate"),
        exportValue: (row: (typeof searchResults)[number]) => row.predicate,
      },
      {
        key: "object",
        header: t("pages.lex.columns.object"),
        exportValue: (row: (typeof searchResults)[number]) => row.object_name,
      },
      {
        key: "fact",
        header: t("pages.lex.columns.fact"),
        exportValue: (row: (typeof searchResults)[number]) => row.fact_text,
      },
      {
        key: "type",
        header: t("pages.lex.columns.type"),
        exportValue: (row: (typeof searchResults)[number]) => row.norm_type,
      },
      {
        key: "document",
        header: t("pages.lex.columns.document"),
        exportValue: (row: (typeof searchResults)[number]) =>
          row.provision_citation
            ? `${row.doc_name} (${row.provision_citation})`
            : row.doc_name,
      },
      {
        key: "confidence",
        header: t("pages.lex.columns.confidence"),
        exportValue: (row: (typeof searchResults)[number]) => row.confidence,
      },
    ],
    [searchResults, t],
  );

  useEffect(() => {
    setOutputDir(lexSearch.outputDir ?? DEFAULT_LEX_OUTPUT_DIR);
    setActivePipelineId(lexSearch.pipelineId ?? null);
    setSearchQuery(lexSearch.q ?? "");
    setResume(lexSearch.resume ?? false);
  }, [
    lexSearch.outputDir,
    lexSearch.pipelineId,
    lexSearch.q,
    lexSearch.resume,
  ]);

  return (
    <div className="space-y-6" data-testid="lex-page">
      <Card>
        <p className="text-muted text-xs font-semibold tracking-[0.24em] uppercase">
          {t("pages.lex.title")}
        </p>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-3xl font-semibold">
              {t("pages.lex.heroTitle")}
            </h2>
            <p className="text-muted mt-2 max-w-3xl text-sm">
              {t("pages.lex.subtitle")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="border-accent/20 bg-accent/10 text-accent rounded-full border px-3 py-1 text-xs font-semibold">
              {(capabilitiesQuery.data?.features ?? []).find(
                (feature) => feature.key === "lex_pipeline",
              )?.label ?? t("pages.lex.featureLabel")}
            </span>
            <PrefetchButton
              to="/runs"
              prefetch="intent"
              size="sm"
              variant="ghost"
            >
              {t("shell.nav.runsDecisions")}
            </PrefetchButton>
            <PrefetchButton
              to="/evidence"
              prefetch="intent"
              size="sm"
              variant="ghost"
            >
              {t("shell.nav.evidenceFabric")}
            </PrefetchButton>
          </div>
        </div>
      </Card>

      {/* ---- Pipeline Control ---- */}
      <Card>
        <h3 className="text-muted mb-3 text-sm font-semibold tracking-wider uppercase">
          {t("pages.lex.pipelineControl")}
        </h3>

        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="text-muted mb-1 block text-xs">
                {t("pages.lex.cardsXmlPath")}
              </label>
              <input
                id="lex-cards-path"
                type="text"
                value={cardsPath}
                onChange={(e) => setCardsPath(e.target.value)}
                aria-label={t("pages.lex.cardsXmlPath")}
                className="border-line bg-surface w-full rounded-lg border px-3 py-1.5 font-mono text-xs"
              />
            </div>
            <div>
              <label className="text-muted mb-1 block text-xs">
                {t("pages.lex.textsXmlPath")}
              </label>
              <input
                id="lex-texts-path"
                type="text"
                value={textsPath}
                onChange={(e) => setTextsPath(e.target.value)}
                aria-label={t("pages.lex.textsXmlPath")}
                className="border-line bg-surface w-full rounded-lg border px-3 py-1.5 font-mono text-xs"
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="text-muted mb-1 block text-xs">
                {t("pages.lex.outputDirectory")}
              </label>
              <input
                id="lex-output-dir"
                type="text"
                value={outputDir}
                onChange={(e) => {
                  const value = e.target.value;
                  setOutputDir(value);
                  updateShareState({ outputDir: value }, { replace: true });
                }}
                aria-label={t("pages.lex.outputDirectory")}
                className="border-line bg-surface w-full rounded-lg border px-3 py-1.5 font-mono text-xs"
              />
            </div>
            <div>
              <label className="text-muted mb-1 block text-xs">
                {t("pages.lex.llmModel")}
              </label>
              <input
                id="lex-llm-model"
                type="text"
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                aria-label={t("pages.lex.llmModel")}
                className="border-line bg-surface w-full rounded-lg border px-3 py-1.5 font-mono text-xs"
              />
            </div>
            <div>
              <label className="text-muted mb-1 block text-xs">
                {t("pages.lex.statusFilter")}
              </label>
              <input
                id="lex-status-filter"
                type="text"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                placeholder={t("pages.lex.statusFilterPlaceholder")}
                aria-label={t("pages.lex.statusFilter")}
                className="border-line bg-surface w-full rounded-lg border px-3 py-1.5 text-xs"
              />
            </div>
          </div>

          {/* Stage toggles */}
          <div>
            <label className="text-muted mb-2 block text-xs">
              {t("pages.lex.stages")}
            </label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(stages) as (keyof typeof stages)[]).map((stage) => (
                <label
                  key={stage}
                  className="hover:bg-text/5 border-line flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs"
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
              <label className="hover:bg-text/5 border-line flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs">
                <input
                  type="checkbox"
                  checked={resume}
                  onChange={() => {
                    const next = !resume;
                    setResume(next);
                    updateShareState({ resume: next }, { replace: true });
                  }}
                  className="accent-accent"
                />
                {t("pages.lex.resume")}
              </label>
            </div>
          </div>

          <button
            type="button"
            disabled={triggerMutation.isPending || isRunning}
            onClick={handleTrigger}
            className="hover:bg-accent/90 bg-accent rounded-xl px-6 py-2.5 text-sm font-semibold text-white transition disabled:opacity-50"
          >
            {triggerMutation.isPending
              ? t("pages.lex.launching")
              : isRunning
                ? t("pages.lex.pipelineRunning")
                : t("pages.lex.launchPipeline")}
          </button>

          {Boolean(triggerMutation.error) && (
            <ApiErrorAlert error={triggerMutation.error} />
          )}

          {triggerMutation.data &&
            triggerMutation.data.status === "accepted" && (
              <p className="text-sm text-green-500">
                {triggerMutation.data.message}
              </p>
            )}
          {triggerMutation.data &&
            triggerMutation.data.status === "rejected" && (
              <p className="text-sm text-red-500">
                {triggerMutation.data.message}
              </p>
            )}
        </div>
      </Card>

      {/* ---- Pipeline Status (shown when active) ---- */}
      {activePipelineId && (
        <Card>
          <h3 className="text-muted mb-3 text-sm font-semibold tracking-wider uppercase">
            {t("pages.lex.pipelineStatus")}
          </h3>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-muted font-mono text-xs">
                {activePipelineId}
              </span>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
                  pipelineState === "completed" &&
                    "bg-green-500/10 text-green-500",
                  pipelineState === "running" && "bg-blue-500/10 text-blue-500",
                  pipelineState === "pending" &&
                    "bg-yellow-500/10 text-yellow-500",
                  pipelineState === "failed" && "bg-red-500/10 text-red-500",
                )}
              >
                {pipelineState ?? t("common.unknown")}
              </span>
            </div>

            {statusQuery.data?.error_message && (
              <p className="text-xs text-red-500">
                {statusQuery.data.error_message}
              </p>
            )}

            {statusQuery.data?.progress_summary &&
              Object.keys(statusQuery.data.progress_summary).length > 0 && (
                <div className="mt-2">
                  <p className="text-muted mb-1 text-xs">
                    {t("pages.lex.progress")}
                  </p>
                  <div className="flex flex-wrap gap-3">
                    {Object.entries(statusQuery.data.progress_summary).map(
                      ([stage, count]) => (
                        <span key={stage} className="text-xs">
                          <span className="text-muted">{stage}:</span>{" "}
                          <span className="font-semibold">
                            {formatNumber(count)}
                          </span>
                        </span>
                      ),
                    )}
                  </div>
                </div>
              )}
          </div>
        </Card>
      )}

      {/* ---- Graph Statistics ---- */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-muted text-sm font-semibold tracking-wider uppercase">
            {t("pages.lex.graphStatistics")}
          </h3>
          <button
            type="button"
            onClick={() => statsQuery.refetch()}
            disabled={statsQuery.isFetching}
            className="hover:bg-text/5 border-line text-muted rounded-lg border px-3 py-1 text-xs transition disabled:opacity-50"
          >
            {statsQuery.isFetching ? t("common.loading") : t("common.refresh")}
          </button>
        </div>

        {statsQuery.error && <ApiErrorAlert error={statsQuery.error} />}

        {statsQuery.data && !statsQuery.data.db_exists && (
          <p className="text-muted text-sm">
            {t("pages.lex.noKnowledgeGraph", { outputDir })}
          </p>
        )}

        {statsQuery.data && statsQuery.data.db_exists && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="border-line bg-surface rounded-xl border p-3 text-center">
                <p className="text-2xl font-bold">
                  {formatNumber(statsQuery.data.total_entities)}
                </p>
                <p className="text-muted text-xs">{t("pages.lex.entities")}</p>
              </div>
              <div className="border-line bg-surface rounded-xl border p-3 text-center">
                <p className="text-2xl font-bold">
                  {formatNumber(statsQuery.data.total_facts)}
                </p>
                <p className="text-muted text-xs">{t("pages.lex.facts")}</p>
              </div>
              <div className="border-line bg-surface rounded-xl border p-3 text-center">
                <p className="text-2xl font-bold">
                  {formatNumber(statsQuery.data.total_provisions)}
                </p>
                <p className="text-muted text-xs">
                  {t("pages.lex.provisions")}
                </p>
              </div>
            </div>

            {topPredicates.length > 0 && (
              <div>
                <p className="text-muted mb-2 text-xs font-semibold">
                  {t("pages.lex.topPredicates")}
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-line text-muted border-b">
                        <th className="px-2 py-1">
                          {t("pages.lex.columns.predicate")}
                        </th>
                        <th className="px-2 py-1 text-right">
                          {t("pages.lex.columns.count")}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {topPredicates.map((predicate) => (
                        <tr
                          key={predicate.predicate}
                          className="border-line/50 border-b"
                        >
                          <td className="px-2 py-1 font-mono">
                            {predicate.predicate}
                          </td>
                          <td className="px-2 py-1 text-right">
                            {formatNumber(predicate.count)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {topEntityTypes.length > 0 && (
              <div>
                <p className="text-muted mb-2 text-xs font-semibold">
                  {t("pages.lex.entityTypes")}
                </p>
                <div className="flex flex-wrap gap-2">
                  {topEntityTypes.map((entityType) => (
                    <span
                      key={entityType.entityType}
                      className="bg-text/5 rounded-lg px-2 py-1 font-mono text-[10px]"
                    >
                      {entityType.entityType}:{" "}
                      {formatNumber(entityType.count)}
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
        <h3 className="text-muted mb-3 text-sm font-semibold tracking-wider uppercase">
          {t("pages.lex.knowledgeSearch")}
        </h3>

        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                const value = e.target.value;
                setSearchQuery(value);
                updateShareState({ q: value }, { replace: true });
              }}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder={t("pages.lex.searchPlaceholder")}
              aria-label={t("pages.lex.knowledgeSearch")}
              className="border-line bg-surface flex-1 rounded-lg border px-3 py-2 text-sm"
            />
            <button
              type="button"
              disabled={searchMutation.isPending || !searchQuery.trim()}
              onClick={handleSearch}
              className="hover:bg-accent/90 bg-accent rounded-xl px-5 py-2 text-sm font-semibold text-white transition disabled:opacity-50"
            >
              {searchMutation.isPending
                ? t("pages.lex.searching")
                : t("pages.lex.search")}
            </button>
          </div>

          {Boolean(searchMutation.error) && (
            <ApiErrorAlert error={searchMutation.error} />
          )}

          {searchMutation.data && searchResults.length === 0 && (
            <p className="text-muted text-sm">
              {t("pages.lex.noResults", { query: searchMutation.data.query })}
            </p>
          )}

          {searchMutation.data && searchResults.length > 0 && (
            <div>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-muted text-xs">
                  {t("pages.lex.resultsSummary", {
                    count: searchMutation.data.total,
                    query: searchMutation.data.query,
                  })}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    onClick={() =>
                      void copyShareLink(
                        new URL(
                          window.location.pathname + window.location.search,
                          window.location.origin,
                        ),
                      )
                    }
                    variant="ghost"
                  >
                    {t("common.shareView")}
                  </Button>
                  <Button
                    type="button"
                    onClick={() =>
                      exportCsv(
                        "lex-search-results.csv",
                        searchResults,
                        searchColumns,
                      )
                    }
                    variant="ghost"
                  >
                    {t("common.exportCsv")}
                  </Button>
                  <Button
                    type="button"
                    onClick={() =>
                      exportJson("lex-search-results.json", {
                        outputDir,
                        query: searchMutation.data?.query ?? searchQuery,
                        results: searchResults,
                      })
                    }
                    variant="ghost"
                  >
                    {t("common.exportJson")}
                  </Button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-line text-muted border-b">
                      <th className="px-2 py-1">
                        {t("pages.lex.columns.subject")}
                      </th>
                      <th className="px-2 py-1">
                        {t("pages.lex.columns.predicate")}
                      </th>
                      <th className="px-2 py-1">
                        {t("pages.lex.columns.object")}
                      </th>
                      <th className="px-2 py-1">
                        {t("pages.lex.columns.fact")}
                      </th>
                      <th className="px-2 py-1">
                        {t("pages.lex.columns.type")}
                      </th>
                      <th className="px-2 py-1">
                        {t("pages.lex.columns.document")}
                      </th>
                      <th className="px-2 py-1 text-right">
                        {t("pages.lex.columns.confidence")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {searchResults.map((r) => (
                      <tr key={r.fact_id} className="border-line/50 border-b">
                        <td className="px-2 py-1 font-mono text-[10px]">
                          {r.subject_name}
                        </td>
                        <td className="text-accent px-2 py-1 font-mono text-[10px]">
                          {r.predicate}
                        </td>
                        <td className="px-2 py-1 font-mono text-[10px]">
                          {r.object_name}
                        </td>
                        <td className="max-w-xs truncate px-2 py-1">
                          {r.fact_text}
                        </td>
                        <td className="px-2 py-1">
                          <span
                            className={cn(
                              "rounded px-1.5 py-0.5 text-[10px] font-semibold",
                              r.norm_type === "obligation" &&
                                "bg-blue-500/10 text-blue-500",
                              r.norm_type === "prohibition" &&
                                "bg-red-500/10 text-red-500",
                              r.norm_type === "permission" &&
                                "bg-green-500/10 text-green-500",
                              r.norm_type === "definition" &&
                                "bg-purple-500/10 text-purple-500",
                            )}
                          >
                            {r.norm_type}
                          </span>
                        </td>
                        <td className="text-muted max-w-[200px] truncate px-2 py-1">
                          {r.doc_name}
                          {r.provision_citation && (
                            <span className="ml-1 text-[10px]">
                              ({r.provision_citation})
                            </span>
                          )}
                        </td>
                        <td className="px-2 py-1 text-right">
                          {r.confidence.toFixed(2)}
                        </td>
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
