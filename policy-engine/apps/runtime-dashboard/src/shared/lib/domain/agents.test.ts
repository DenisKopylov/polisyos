import { normalizeAgentPipeline } from "@/shared/lib/domain/agents";

describe("agents domain", () => {
  it("classifies performance budget labels as diagnostic interaction state", () => {
    const model = normalizeAgentPipeline({
      performance_summary: {
        phase_budgets: [
          {
            phase: "retrieval",
            status: "over_budget",
          },
        ],
      },
    });

    expect(model.performanceSummary?.phaseBudgets[0]?.status).toMatchObject({
      authorityPurpose: "diagnostic_display",
      label: "over_budget",
      purpose: "interaction_only",
    });
  });

  it("normalizes agent pipeline payloads into sorted attempts and steps", () => {
    const model = normalizeAgentPipeline({
      attempts: [
        {
          attempt: "2",
          duration_ms: "3500",
          finished_at: "2026-03-09T10:00:40Z",
          notes: ["attempt-note", 2],
          started_at: "2026-03-09T10:00:05Z",
          status: "running",
          steps: [
            {
              action: "run_plan",
              agent: "executor",
              status: "warn",
              timestamp: "2026-03-09T10:00:20Z",
            },
            {
              action: "draft",
              agent: "pi_decompose",
              details: { mode: "nl" },
              prompt: "prompt",
              status: "ok",
              timestamp: "2026-03-09T10:00:10Z",
              token_usage: {
                completion_tokens: "15",
                prompt_tokens: "10",
                total_tokens: "25",
              },
            },
            {
              action: "review",
              agent: "critic_review",
              response: "response",
              status: "FAIL",
              timestamp: "2026-03-09T10:00:20Z",
            },
            {
              agent: "custom_agent",
              provider: "internal",
            },
          ],
          verdict: "REVIEW",
        },
        {
          attempt: 1,
          steps: [
            {
              action: "normalize",
              agent: "formalize",
              timestamp: "2026-03-09T09:59:00Z",
            },
          ],
        },
      ],
      evaluator: {
        reasons: ["reason-1", 1],
        replanning_hints: ["hint-1", null],
        scores: {
          budget_score: "0.6",
          constraints_score: "0.9",
          data_quality_score: "0.7",
          kpi_score: "0.8",
          total_score: "0.75",
          uncertainty_score: "0.5",
        },
        verdict: "REVIEW",
      },
      iteration_lifecycle: {
        iteration: 0,
        last_verdict: "approve",
        notes: ["iter"],
        state: "stopped",
        stop_reason: "converged",
      },
      latest_verdict: "approve",
      notes: ["pipeline-note", 9],
      performance_summary: {
        llm: {
          latency_ms: "125000",
          total_tokens: "3400",
        },
        phase_budgets: [
          {
            budget_ms: "10000",
            category: "retrieval",
            duration_ms: "15000",
            phase: "retrieval.materialize",
            status: "over_budget",
          },
          {
            budget_ms: 20000,
            category: "llm",
            duration_ms: 12000,
            phase: "llm.total",
            status: "within_budget",
          },
        ],
        variants: {
          completed: "1",
          failed: "1",
          total: "2",
        },
      },
      preflight: {
        diagnostics: [
          {
            code: "missing_binding",
            message: "Need binding",
            path: ["plan", 0],
            replanning_hints: ["add-binding", null],
            severity: "warning",
          },
          null,
        ],
        notes: ["preflight", 1],
        ready_to_run: 1,
      },
      reproducibility: {
        data_snapshot_hash: "data-hash",
        input_bindings_hash: "input-hash",
        method_catalog_hash: "method-hash",
        notes: ["repro", 1],
        plan_hash: "plan-hash",
        registry_hash: "registry-hash",
        seed: -5,
      },
      retrieval: {
        candidates_filtered: "3",
        candidates_promoted: "1",
        lane_used: "fastlane",
        local_index_docs_total: "40",
        local_index_size_bytes: "1024",
        metadata_docs_fetched: "5",
        mode: "local",
        notes: ["retrieval-note", 7],
        phases: [
          {
            candidates_selected: "3",
            candidates_total: "10",
            docs_fetched: "4",
            duration_ms: "12",
            lane: "fastlane",
            phase: "search",
          },
          {
            docs_fetched: 5,
          },
        ],
      },
      run_id: "run-1",
      source: "natural_language",
      total_attempts: "3",
    });

    expect(model).toEqual({
      attempts: [
        {
          attempt: 1,
          costOriginCounts: {},
          costUsd: null,
          durationMs: null,
          estimatedCostUsd: null,
          finishedAt: null,
          notes: [],
          startedAt: null,
          status: "unknown",
          reportedCostUsd: null,
          settlementStatusCounts: {},
          steps: [
            {
              action: "normalize",
              actionLabel: "Normalize",
              agent: "formalizer",
              agentLabel: "Formalizer",
              attempt: 1,
              completionTokens: null,
              costUsd: null,
              costUnknown: false,
              costEvents: [],
              details: {},
              latencyMs: null,
              model: null,
              modelVariantId: null,
              prompt: null,
              promptTokens: null,
              provider: null,
              response: null,
              status: "info",
              summary: null,
              timestamp: "2026-03-09T09:59:00Z",
              totalTokens: null,
            },
          ],
          verdict: null,
        },
        {
          attempt: 2,
          costOriginCounts: {},
          costUsd: null,
          durationMs: 3500,
          estimatedCostUsd: null,
          finishedAt: "2026-03-09T10:00:40Z",
          notes: ["attempt-note", "2"],
          startedAt: "2026-03-09T10:00:05Z",
          status: "running",
          reportedCostUsd: null,
          settlementStatusCounts: {},
          steps: [
            expect.objectContaining({
              action: "draft",
              actionLabel: "Draft",
              agent: "pi_agent",
              agentLabel: "PI Agent",
              details: { mode: "nl" },
              prompt: "prompt",
              promptTokens: 10,
              status: "ok",
              totalTokens: 25,
            }),
            expect.objectContaining({
              action: "run_plan",
              agent: "executor",
              agentLabel: "Executor",
              status: "warn",
            }),
            expect.objectContaining({
              action: "review",
              agent: "critic",
              agentLabel: "Critic",
              response: "response",
              status: "fail",
            }),
            expect.objectContaining({
              action: "unknown",
              agent: "custom_agent",
              agentLabel: "Custom Agent",
              provider: "internal",
              status: "info",
            }),
          ],
          verdict: "REVIEW",
        },
      ],
      evaluator: {
        reasons: ["reason-1", "1"],
        replanningHints: ["hint-1"],
        scores: {
          budgetScore: 0.6,
          constraintsScore: 0.9,
          dataQualityScore: 0.7,
          kpiScore: 0.8,
          totalScore: 0.75,
          uncertaintyScore: 0.5,
        },
        verdict: "REVIEW",
      },
      hasPromptData: true,
      costOriginCounts: {},
      costUsd: null,
      estimatedCostUsd: null,
      iterationLifecycle: {
        iteration: 1,
        lastVerdict: "approve",
        notes: ["iter"],
        state: "stopped",
        stopReason: "converged",
      },
      latestVerdict: "approve",
      notes: ["pipeline-note", "9"],
      performanceSummary: {
        llmLatencyMs: 125000,
        overBudgetCount: 1,
        phaseBudgets: [
          {
            budgetMs: 10000,
            category: "retrieval",
            durationMs: 15000,
            phase: "retrieval.materialize",
            status: expect.objectContaining({
              authorityPurpose: "diagnostic_display",
              label: "over_budget",
              purpose: "interaction_only",
            }),
          },
          {
            budgetMs: 20000,
            category: "llm",
            durationMs: 12000,
            phase: "llm.total",
            status: expect.objectContaining({
              authorityPurpose: "diagnostic_display",
              label: "within_budget",
              purpose: "interaction_only",
            }),
          },
        ],
        totalTokens: 3400,
        variantsCompleted: 1,
        variantsFailed: 1,
        variantsTotal: 2,
      },
      preflight: {
        diagnostics: [
          {
            code: "missing_binding",
            message: "Need binding",
            path: ["plan", "0"],
            replanningHints: ["add-binding"],
            severity: "warning",
          },
        ],
        notes: ["preflight", "1"],
        readyToRun: true,
      },
      reproducibility: {
        dataSnapshotHash: "data-hash",
        inputBindingsHash: "input-hash",
        methodCatalogHash: "method-hash",
        notes: ["repro", "1"],
        planHash: "plan-hash",
        registryHash: "registry-hash",
        seed: 0,
      },
      retrieval: {
        candidatesFiltered: 3,
        candidatesPromoted: 1,
        laneUsed: "fastlane",
        localIndexDocsTotal: 40,
        localIndexSizeBytes: 1024,
        metadataDocsFetched: 5,
        mode: "local",
        notes: ["retrieval-note", "7"],
        phases: [
          {
            candidatesSelected: 3,
            candidatesTotal: 10,
            docsFetched: 4,
            durationMs: 12,
            lane: "fastlane",
            phase: "search",
          },
        ],
      },
      runId: "run-1",
      reportedCostUsd: null,
      settlementStatusCounts: {},
      source: "natural_language",
      totalAttempts: 3,
    });
  });

  it("returns safe defaults for empty or malformed payloads", () => {
    expect(normalizeAgentPipeline(null)).toEqual({
      attempts: [],
      costOriginCounts: {},
      costUsd: null,
      estimatedCostUsd: null,
      evaluator: null,
      hasPromptData: false,
      iterationLifecycle: null,
      latestVerdict: null,
      notes: [],
      performanceSummary: null,
      preflight: null,
      reproducibility: null,
      reportedCostUsd: null,
      retrieval: null,
      runId: "unknown",
      settlementStatusCounts: {},
      source: null,
      totalAttempts: 0,
    });
  });

  it("keeps unknown producer costs null and preserves reuse lineage", () => {
    const model = normalizeAgentPipeline({
      attempts: [
        {
          attempt: 1,
          steps: [
            {
              action: "draft",
              agent: "drafter",
              cost_events: [
                {
                  amount: "0",
                  cost_origin: "reported",
                  cost_usd: 0,
                  durability: "ledger",
                  event_id: "provider:zero",
                  payload_digest: "sha256:reported",
                  provider: "gateway",
                  receipts: ["provider:zero"],
                  settlement_status: "committed",
                },
                {
                  amount: null,
                  cost_origin: "unknown",
                  cost_usd: null,
                  durability: "none",
                  event_id: "provider:unknown",
                  payload_digest: "sha256:unknown",
                  provider: "gateway",
                  receipts: [],
                  settlement_status: "unknown",
                },
                {
                  amount: "0",
                  cost_origin: "reuse",
                  cost_usd: 0,
                  durability: "ledger",
                  event_id: "cache:reuse",
                  origin_event_id: "provider:zero",
                  payload_digest: "sha256:reuse",
                  provider: "gateway",
                  receipts: ["cache:reuse"],
                  settlement_status: "committed",
                },
              ],
            },
          ],
        },
      ],
    });

    const step = model.attempts[0]?.steps[0];
    expect(model.costUsd).toBeNull();
    expect(model.reportedCostUsd).toBe(0);
    expect(model.costOriginCounts).toEqual({
      reported: 1,
      unknown: 1,
      reuse: 1,
    });
    expect(step?.costUsd).toBeNull();
    expect(step?.costUnknown).toBe(true);
    expect(step?.costEvents[0]?.costUsd).toBe(0);
    expect(step?.costEvents[1]?.costUsd).toBeNull();
    expect(step?.costEvents[2]?.originEventId).toBe("provider:zero");
  });
});
