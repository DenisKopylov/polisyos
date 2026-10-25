import {
  normalizeAgentPipeline,
  summarizeAgentCostEvents,
} from "@/shared/lib/domain/agents";

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
          unattributedCostScalars: [],
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
              ownerCostUnknown: false,
              costEvents: [],
              unattributedCostScalars: [],
              details: {},
              detailsCostScope: "not_established",
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
          unattributedCostScalars: [],
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
      ownerControlJobAttempt: null,
      reportedCostUsd: null,
      settlementStatusCounts: {},
      source: "natural_language",
      totalAttempts: 3,
      unattributedCostEvents: [],
      unattributedCostScalars: [],
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
      ownerControlJobAttempt: null,
      settlementStatusCounts: {},
      source: null,
      totalAttempts: 0,
      unattributedCostEvents: [],
      unattributedCostScalars: [],
    });
  });

  it("keeps lease-unattributed rows visible without charging the attempt summary", () => {
    const model = normalizeAgentPipeline({
      attempts: [],
      unattributed_cost_events: [
        {
          amount: "0.05",
          control_job_attempt: null,
          cost_origin: "estimated",
          cost_usd: 0.05,
          durability: "ledger",
          event_id: "preflight:event",
          pre_admission_attempt_id: "0123456789abcdef0123456789abcdef",
          payload_digest: "sha256:preflight",
          receipts: ["preflight:event"],
          settlement_status: "committed",
        },
      ],
    });

    expect(model.unattributedCostEvents).toEqual([
      expect.objectContaining({
        controlJobAttempt: null,
        costOrigin: "estimated",
        eventId: "preflight:event",
        preAdmissionAttemptId: "0123456789abcdef0123456789abcdef",
      }),
    ]);
    expect(model.costUsd).toBeNull();
    expect(model.estimatedCostUsd).toBeNull();
    expect(model.costOriginCounts).toEqual({});
  });

  it("keeps unknown producer costs null and preserves reuse lineage", () => {
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 1,
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
                  control_job_attempt: 1,
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
                  control_job_attempt: 1,
                  cost_usd: null,
                  durability: "ledger",
                  event_id: "provider:unknown",
                  payload_digest: "sha256:unknown",
                  provider: "gateway",
                  receipts: [],
                  settlement_status: "unknown",
                },
                {
                  amount: "0",
                  cost_origin: "reuse",
                  control_job_attempt: 1,
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

  it("keeps eventless scalar claims out of current totals and excludes stale lease attempts", () => {
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 2,
      cost_usd: 0.82,
      reported_cost_usd: 0.82,
      attempts: [
        {
          attempt: 2,
          cost_usd: 0.53,
          reported_cost_usd: 0.53,
          steps: [
            {
              action: "durable_ledger",
              agent: "llm_producer_settlement",
              attempt: 2,
              cost_usd: 0.41,
              model_variant_id: "legacy-top-level-variant",
            },
            {
              action: "durable_ledger",
              agent: "llm_producer_settlement",
              attempt: 2,
              model_variant_id: "legacy-nested-variant",
              cost_events: [
                {
                  amount: "0.23",
                  cost_origin: "reported",
                  control_job_attempt: 1,
                  cost_usd: 0.23,
                  durability: "ledger",
                  event_id: "prior-attempt-event",
                  receipts: ["prior-attempt-event"],
                  settlement_status: "committed",
                },
                {
                  amount: "0.03",
                  cost_origin: "reported",
                  control_job_attempt: 2,
                  cost_usd: 0.03,
                  durability: "ledger",
                  event_id: "current-attempt-event",
                  receipts: ["current-attempt-event"],
                  settlement_status: "committed",
                },
              ],
            },
          ],
        },
      ],
    });

    const attempt = model.attempts[0];
    const scalarStep = attempt?.steps[0];
    const ledgerStep = attempt?.steps[1];
    expect(model.costUsd).toBe(0.03);
    expect(model.reportedCostUsd).toBe(0.03);
    expect(attempt?.costUsd).toBe(0.03);
    expect(scalarStep?.costUsd).toBeNull();
    expect(scalarStep?.costUnknown).toBe(true);
    expect(scalarStep?.unattributedCostScalars).toEqual([
      expect.objectContaining({
        claimedValueUsd: 0.41,
        scope: "not_established",
        sourceField: "cost_usd",
        sourceKind: "step_summary",
      }),
    ]);
    expect(ledgerStep?.costUsd).toBe(0.03);
    expect(ledgerStep?.costUnknown).toBe(false);
    expect(ledgerStep?.costEvents[0]?.currentOwnerEligible).toBe(false);
    expect(ledgerStep?.costEvents[0]?.costUsd).toBeNull();
    expect(ledgerStep?.costEvents[1]?.currentOwnerEligible).toBe(true);
    expect(model.unattributedCostScalars).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          claimedValueUsd: 0.82,
          scope: "not_established",
          sourceKind: "pipeline_summary",
        }),
      ]),
    );
    expect(
      model.unattributedCostScalars.some(
        (scalar) => scalar.claimedValueUsd === 0.23,
      ),
    ).toBe(false);

    const pipelineOnlyClaim = normalizeAgentPipeline({ cost_usd: 0.01 });
    expect(pipelineOnlyClaim.costUsd).toBeNull();
    expect(pipelineOnlyClaim.unattributedCostScalars).toEqual([
      expect.objectContaining({
        claimedValueUsd: 0.01,
        scope: "not_established",
        sourceField: "cost_usd",
        sourceKind: "pipeline_summary",
      }),
    ]);
  });

  it("separates current-owner unknowns from stale, unowned, and legacy claims", () => {
    const ownerEvent = {
      event_id: "provider:owner-known",
      cost_origin: "reported",
      amount: "0.25",
      cost_usd: 0.25,
      settlement_status: "committed",
      durability: "ledger",
      control_job_attempt: 2,
      pre_admission_attempt_id: null,
      payload_digest: "sha256:owner-known",
    };
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 2,
      attempts: [
        {
          attempt: 1,
          steps: [
            {
              agent: "model_variant",
              action: "stale same identity",
              model_variant_id: "shared-v",
              cost_events: [
                {
                  ...ownerEvent,
                  amount: "9.00",
                  cost_usd: 9,
                  control_job_attempt: 1,
                  payload_digest: "sha256:stale",
                },
              ],
            },
          ],
        },
        {
          attempt: 2,
          steps: [
            {
              agent: "model_variant",
              action: "owner projection",
              model_variant_id: "shared-v",
              cost_usd: 0.25,
              reported_cost_usd: 0.25,
              cost_events: [ownerEvent],
            },
            {
              agent: "model_variant",
              action: "unowned memory",
              model_variant_id: "shared-v",
              cost_events: [
                {
                  event_id: "provider:unowned-memory",
                  cost_origin: "unknown",
                  amount: null,
                  cost_usd: null,
                  settlement_status: "unknown",
                  durability: "memory",
                  control_job_attempt: null,
                  pre_admission_attempt_id: null,
                },
              ],
            },
            {
              agent: "model_variant",
              action: "unscoped legacy claim",
              model_variant_id: "shared-v",
              cost_usd: 0.8,
            },
            {
              agent: "model_variant",
              action: "owner unknown",
              model_variant_id: "shared-v",
              cost_events: [
                {
                  event_id: "provider:owner-unknown",
                  cost_origin: "unknown",
                  amount: null,
                  cost_usd: null,
                  settlement_status: "unknown",
                  durability: "ledger",
                  control_job_attempt: 2,
                  pre_admission_attempt_id: null,
                },
              ],
            },
          ],
        },
      ],
    });
    const steps = model.attempts.flatMap((attempt) => attempt.steps);
    const stale = steps.find((step) => step.action === "stale same identity");
    const owner = steps.find((step) => step.action === "owner projection");
    const memory = steps.find((step) => step.action === "unowned memory");
    const legacy = steps.find(
      (step) => step.action === "unscoped legacy claim",
    );
    const unknown = steps.find((step) => step.action === "owner unknown");

    expect(model.costUsd).toBeNull();
    expect(model.reportedCostUsd).toBe(0.25);
    expect(stale?.costUnknown).toBe(true);
    expect(stale?.ownerCostUnknown).toBe(false);
    expect(owner?.costUsd).toBe(0.25);
    expect(owner?.costUnknown).toBe(false);
    expect(owner?.ownerCostUnknown).toBe(false);
    expect(owner?.unattributedCostScalars).toEqual([]);
    expect(memory?.costUnknown).toBe(true);
    expect(memory?.ownerCostUnknown).toBe(false);
    expect(legacy?.costUnknown).toBe(true);
    expect(legacy?.ownerCostUnknown).toBe(false);
    expect(legacy?.unattributedCostScalars).toEqual([
      expect.objectContaining({
        claimedValueUsd: 0.8,
        scope: "not_established",
      }),
    ]);
    expect(unknown?.ownerCostUnknown).toBe(true);
    expect(
      summarizeAgentCostEvents(
        [
          ...(owner?.costEvents ?? []),
          ...(stale?.costEvents ?? []),
          ...(memory?.costEvents ?? []),
        ],
        model.ownerControlJobAttempt,
      ),
    ).toMatchObject({
      costUsd: 0.25,
      reportedCostUsd: 0.25,
      costCompleteness: "complete",
      costUnknown: false,
    });
    expect(
      summarizeAgentCostEvents(
        [...(owner?.costEvents ?? []), ...(unknown?.costEvents ?? [])],
        model.ownerControlJobAttempt,
      ),
    ).toMatchObject({
      reportedCostUsd: 0.25,
      costCompleteness: "partial_unknown",
      costUnknown: true,
    });
  });

  it("uses the verified owner attempt rather than the enclosing variant ordinal", () => {
    const payload = {
      owner_control_job_attempt: 2,
      attempts: [
        {
          attempt: 1,
          steps: [
            {
              agent: "llm_producer_settlement",
              action: "durable_ledger",
              cost_events: [
                {
                  event_id: "provider:prior-attempt",
                  cost_origin: "reported",
                  amount: "0.12",
                  cost_usd: 0.12,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 1,
                  pre_admission_attempt_id: null,
                  receipts: ["provider:prior-attempt"],
                },
                {
                  event_id: "provider:owner-attempt",
                  cost_origin: "reported",
                  amount: "0.01",
                  cost_usd: 0.01,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 2,
                  pre_admission_attempt_id: null,
                  receipts: ["provider:owner-attempt"],
                },
              ],
            },
          ],
        },
        {
          attempt: 2,
          steps: [
            {
              agent: "model_variant",
              action: "completed",
              model_variant_id: "shared-owner-variant",
              cost_events: [
                {
                  event_id: "provider:variant-a",
                  cost_origin: "reported",
                  amount: "0.02",
                  cost_usd: 0.02,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 2,
                  pre_admission_attempt_id: null,
                  receipts: ["provider:variant-a"],
                },
              ],
            },
          ],
        },
        {
          attempt: 3,
          steps: [
            {
              agent: "model_variant",
              action: "completed",
              model_variant_id: "shared-owner-variant",
              cost_events: [
                {
                  event_id: "provider:variant-b",
                  cost_origin: "reported",
                  amount: "0.03",
                  cost_usd: 0.03,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 2,
                  pre_admission_attempt_id: null,
                  receipts: ["provider:variant-b"],
                },
              ],
            },
          ],
        },
      ],
    };

    const model = normalizeAgentPipeline(payload);
    expect(model.ownerControlJobAttempt).toBe(2);
    expect(model.attempts.map((attempt) => attempt.attempt)).toEqual([1, 2, 3]);
    expect(model.costUsd).toBeCloseTo(0.06);
    expect(model.reportedCostUsd).toBeCloseTo(0.06);
    expect(model.attempts[0]?.steps[0]?.costUsd).toBe(0.01);
    expect(model.attempts[1]?.steps[0]?.costUsd).toBe(0.02);
    expect(model.attempts[2]?.steps[0]?.costUsd).toBe(0.03);
    expect(model.attempts[0]?.steps[0]?.costEvents).toHaveLength(2);
    expect(
      model.attempts[0]?.steps[0]?.costEvents[0]?.currentOwnerEligible,
    ).toBe(false);
    expect(model.attempts[0]?.steps[0]?.costEvents[0]?.costUsd).toBeNull();
    expect(
      model.attempts[0]?.steps[0]?.costEvents[1]?.currentOwnerEligible,
    ).toBe(true);
    expect(model.attempts[0]?.steps[0]?.costEvents[1]?.costUsd).toBe(0.01);

    const withoutOwner = normalizeAgentPipeline({ attempts: payload.attempts });
    expect(withoutOwner.ownerControlJobAttempt).toBeNull();
    expect(withoutOwner.costUsd).toBeNull();
    expect(withoutOwner.attempts[0]?.steps[0]?.costUsd).toBeNull();
    expect(withoutOwner.attempts[0]?.steps[0]?.costUnknown).toBe(true);
    expect(
      withoutOwner.attempts[0]?.steps[0]?.costEvents[1]?.currentOwnerEligible,
    ).toBe(false);
    expect(
      withoutOwner.attempts[0]?.steps[0]?.costEvents[1]?.costUsd,
    ).toBeNull();
    expect(withoutOwner.attempts[0]?.steps[0]?.costEvents[1]?.amount).toBe(
      "0.01",
    );
  });

  it("keeps opaque detail claims out of current totals and labels their scope", () => {
    const details = {
      nested: { cost_usd: 0.73, reported_cost_usd: 0.81 },
      annotation: "diagnostic $9 only",
    };
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 2,
      attempts: [
        {
          attempt: 1,
          steps: [
            {
              agent: "critic",
              action: "approved",
              details,
              cost_events: [
                {
                  event_id: "owner-attempt-detail-test",
                  cost_origin: "reported",
                  amount: "0.03",
                  cost_usd: 0.03,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 2,
                  pre_admission_attempt_id: null,
                },
              ],
            },
          ],
        },
      ],
    });
    const step = model.attempts[0]?.steps[0];
    expect(step?.detailsCostScope).toBe("not_established");
    expect(step?.details).toEqual(details);
    expect(step?.costUsd).toBe(0.03);
    expect(model.costUsd).toBe(0.03);
  });

  it("keeps ownerless scalar and event inputs unassigned at every projection level", () => {
    const ownerlessAttempts = [
      {
        attempt: 2,
        cost_usd: 0.97,
        reported_cost_usd: 0.96,
        steps: [
          {
            agent: "llm_producer_settlement",
            action: "durable_ledger",
            cost_usd: 0.95,
            reported_cost_usd: 0.94,
            cost_events: [
              {
                event_id: "ownerless-raw-ledger-claim",
                cost_origin: "reported",
                amount: "0.03",
                cost_usd: 0.03,
                settlement_status: "committed",
                durability: "ledger",
                control_job_attempt: 2,
                pre_admission_attempt_id: null,
              },
            ],
          },
        ],
      },
    ];
    const model = normalizeAgentPipeline({
      cost_usd: 0.99,
      reported_cost_usd: 0.98,
      attempts: ownerlessAttempts,
    });

    expect(model.costUsd).toBeNull();
    expect(model.reportedCostUsd).toBeNull();
    expect(model.estimatedCostUsd).toBeNull();
    expect(model.costOriginCounts).toEqual({});
    expect(model.settlementStatusCounts).toEqual({});
    expect(model.attempts[0]?.costUsd).toBeNull();
    expect(model.attempts[0]?.reportedCostUsd).toBeNull();
    expect(model.attempts[0]?.estimatedCostUsd).toBeNull();
    expect(model.attempts[0]?.costOriginCounts).toEqual({});
    expect(model.attempts[0]?.settlementStatusCounts).toEqual({});
    expect(model.attempts[0]?.steps[0]?.costUsd).toBeNull();
    expect(model.attempts[0]?.steps[0]?.unattributedCostScalars).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          claimedValueUsd: 0.95,
          scope: "not_established",
          sourceField: "cost_usd",
          sourceKind: "step_summary",
        }),
        expect.objectContaining({
          claimedValueUsd: 0.94,
          scope: "not_established",
          sourceField: "reported_cost_usd",
          sourceKind: "step_summary",
        }),
      ]),
    );
    expect(model.attempts[0]?.steps[0]?.costEvents[0]?.costUsd).toBeNull();
    expect(model.attempts[0]?.steps[0]?.costEvents[0]?.amount).toBe("0.03");
    expect(
      new Set(model.unattributedCostScalars.map((row) => row.sourceKind)),
    ).toEqual(new Set(["pipeline_summary", "attempt_summary", "step_summary"]));

    const absentEventList = normalizeAgentPipeline({
      owner_control_job_attempt: null,
      cost_usd: 0.11,
      attempts: [
        {
          attempt: 1,
          cost_usd: 0.12,
          steps: [{ agent: "model", action: "legacy", cost_usd: 0.13 }],
        },
      ],
    });
    expect(absentEventList.costUsd).toBeNull();
    expect(absentEventList.attempts[0]?.costUsd).toBeNull();
    expect(absentEventList.attempts[0]?.steps[0]?.costUsd).toBeNull();

    for (const malformedOwner of [true, 0, 2.5, "2"]) {
      const malformed = normalizeAgentPipeline({
        owner_control_job_attempt: malformedOwner,
        cost_usd: 0.01,
        attempts: ownerlessAttempts,
      });
      expect(malformed.ownerControlJobAttempt).toBeNull();
      expect(malformed.costUsd).toBeNull();
      expect(malformed.attempts[0]?.costUsd).toBeNull();
      expect(malformed.attempts[0]?.steps[0]?.costUsd).toBeNull();
      expect(
        malformed.attempts[0]?.steps[0]?.costEvents.every(
          (event) => !event.currentOwnerEligible && event.costUsd === null,
        ),
      ).toBe(true);
    }
  });

  it("keeps reported and estimated costs separate when unknown costs remain", () => {
    const payload = (costEvents: unknown[]) => ({
      owner_control_job_attempt: 1,
      attempts: [
        {
          attempt: 1,
          steps: [
            {
              agent: "model_variant",
              action: "completed",
              cost_events: costEvents,
            },
          ],
        },
      ],
    });
    const model = normalizeAgentPipeline(
      payload([
        {
          event_id: "reported:one",
          cost_origin: "reported",
          amount: "0.02",
          cost_usd: 0.02,
          settlement_status: "committed",
          durability: "ledger",
          control_job_attempt: 1,
        },
        {
          event_id: "estimate:one",
          cost_origin: "estimated",
          amount: "0.03",
          cost_usd: 0.03,
          settlement_status: "committed",
          durability: "ledger",
          control_job_attempt: 1,
        },
        {
          event_id: "unknown:one",
          cost_origin: "unknown",
          amount: null,
          cost_usd: null,
          settlement_status: "unknown",
          durability: "ledger",
          control_job_attempt: 1,
        },
      ]),
    );
    const step = model.attempts[0]?.steps[0];
    const summary = summarizeAgentCostEvents(
      step?.costEvents ?? [],
      model.ownerControlJobAttempt,
      step?.ownerCostUnknown ?? false,
    );

    expect(step?.costUsd).toBeNull();
    expect(step?.costUnknown).toBe(true);
    expect(model.reportedCostUsd).toBe(0.02);
    expect(model.estimatedCostUsd).toBe(0.03);
    expect(summary).toMatchObject({
      reportedCostUsd: 0.02,
      estimatedCostUsd: 0.03,
      costUsd: null,
      costCompleteness: "partial_unknown",
      costUnknown: true,
    });
  });

  it("does not count reuse amounts as newly incurred cost and distinguishes no observation", () => {
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 1,
      attempts: [
        {
          attempt: 1,
          steps: [
            {
              agent: "model_variant",
              action: "completed",
              cost_events: [
                {
                  event_id: "reuse:one",
                  origin_event_id: "reported:original",
                  cost_origin: "reuse",
                  amount: "0.09",
                  cost_usd: 0.09,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 1,
                },
              ],
            },
          ],
        },
      ],
    });
    const step = model.attempts[0]?.steps[0];
    const reuse = summarizeAgentCostEvents(
      step?.costEvents ?? [],
      model.ownerControlJobAttempt,
      step?.ownerCostUnknown ?? false,
    );
    const absent = summarizeAgentCostEvents([], model.ownerControlJobAttempt);

    expect(model.costUsd).toBeNull();
    expect(model.reportedCostUsd).toBeNull();
    expect(model.estimatedCostUsd).toBeNull();
    expect(reuse).toMatchObject({
      costUsd: null,
      reportedCostUsd: null,
      estimatedCostUsd: null,
      costOriginCounts: { reuse: 1 },
      costUnknown: true,
      costCompleteness: "unknown",
    });
    expect(step?.costEvents[0]).toMatchObject({
      costUsd: 0.09,
      originEventId: "reported:original",
    });
    expect(absent).toMatchObject({
      costUsd: null,
      costUnknown: false,
      costCompleteness: "not_observed",
    });
  });

  it("counts one identical producer event once across step, attempt, and pipeline summaries", () => {
    const event = {
      event_id: "provider:shared",
      cost_origin: "reported",
      amount: "0.25",
      cost_usd: 0.25,
      settlement_status: "committed",
      durability: "ledger",
      control_job_attempt: 1,
      pre_admission_attempt_id: null,
      payload_digest: "sha256:shared",
    };
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 1,
      attempts: [
        {
          attempt: 1,
          steps: [
            { agent: "model_variant", action: "first", cost_events: [event] },
            {
              agent: "model_variant",
              action: "duplicate-view",
              cost_events: [event],
            },
          ],
        },
      ],
    });
    const attempt = model.attempts[0];

    expect(attempt?.steps).toHaveLength(2);
    expect(attempt?.costUsd).toBe(0.25);
    expect(attempt?.reportedCostUsd).toBe(0.25);
    expect(attempt?.costOriginCounts).toEqual({ reported: 1 });
    expect(model.costUsd).toBe(0.25);
    expect(model.reportedCostUsd).toBe(0.25);
    expect(model.costOriginCounts).toEqual({ reported: 1 });
    expect(
      summarizeAgentCostEvents(
        attempt?.steps.flatMap((step) => step.costEvents) ?? [],
        model.ownerControlJobAttempt,
      ),
    ).toMatchObject({
      costUsd: 0.25,
      reportedCostUsd: 0.25,
      costOriginCounts: { reported: 1 },
      costCompleteness: "complete",
      costUnknown: false,
    });
  });

  it("resolves identities only across current-owner ledger observations", () => {
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 1,
      attempts: [
        {
          attempt: 1,
          steps: [
            {
              agent: "model_variant",
              action: "current",
              cost_events: [
                {
                  event_id: "provider:current",
                  cost_origin: "reported",
                  amount: "0.25",
                  cost_usd: 0.25,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 1,
                  pre_admission_attempt_id: null,
                  payload_digest: "sha256:current",
                },
              ],
            },
            {
              agent: "model_variant",
              action: "stale-conflict",
              cost_events: [
                {
                  event_id: "provider:current",
                  cost_origin: "estimated",
                  amount: "9.00",
                  cost_usd: 9,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 2,
                  pre_admission_attempt_id: null,
                  payload_digest: "sha256:stale",
                },
              ],
            },
          ],
        },
      ],
    });

    expect(model.reportedCostUsd).toBe(0.25);
    expect(model.estimatedCostUsd).toBeNull();
    expect(model.costOriginCounts).toEqual({ reported: 1 });
    expect(model.costUsd).toBe(0.25);
    const steps = model.attempts[0]?.steps ?? [];
    expect(steps.find((step) => step.action === "current")?.costUnknown).toBe(
      false,
    );
    expect(
      steps.find((step) => step.action === "stale-conflict")?.costUnknown,
    ).toBe(true);
    expect(model.attempts[0]?.reportedCostUsd).toBe(0.25);
    expect(model.attempts[0]?.costOriginCounts).toEqual({ reported: 1 });
    expect(
      summarizeAgentCostEvents(
        model.attempts[0]?.steps.flatMap((step) => step.costEvents) ?? [],
        model.ownerControlJobAttempt,
      ),
    ).toMatchObject({
      reportedCostUsd: 0.25,
      costUnknown: false,
      costCompleteness: "complete",
    });
  });

  it("keeps distinct event identities additive when their amounts match", () => {
    const events = ["provider:first", "provider:second"].map((event_id) => ({
      event_id,
      cost_origin: "reported",
      amount: "0.25",
      cost_usd: 0.25,
      settlement_status: "committed",
      durability: "ledger",
      control_job_attempt: 1,
      pre_admission_attempt_id: null,
    }));
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 1,
      attempts: [
        {
          attempt: 1,
          steps: [
            { agent: "model_variant", action: "done", cost_events: events },
          ],
        },
      ],
    });

    expect(model.reportedCostUsd).toBe(0.5);
    expect(model.costOriginCounts).toEqual({ reported: 2 });
    expect(
      summarizeAgentCostEvents(
        model.attempts[0]?.steps.flatMap((step) => step.costEvents) ?? [],
        model.ownerControlJobAttempt,
      ).costUnknown,
    ).toBe(false);
  });

  it("withholds a conflicting duplicate identity and preserves uncontested subtotals", () => {
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 1,
      attempts: [
        {
          attempt: 1,
          steps: [
            {
              agent: "model_variant",
              action: "done",
              cost_events: [
                {
                  event_id: "provider:conflict",
                  cost_origin: "reported",
                  amount: "0.25",
                  cost_usd: 0.25,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 1,
                  pre_admission_attempt_id: null,
                  payload_digest: "sha256:first",
                },
                {
                  event_id: "provider:conflict",
                  cost_origin: "estimated",
                  amount: "0.75",
                  cost_usd: 0.75,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 1,
                  pre_admission_attempt_id: null,
                  payload_digest: "sha256:conflicting",
                },
                {
                  event_id: "provider:known",
                  cost_origin: "reported",
                  amount: "0.10",
                  cost_usd: 0.1,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 1,
                  pre_admission_attempt_id: null,
                  payload_digest: "sha256:known",
                },
              ],
            },
          ],
        },
      ],
    });

    expect(model.reportedCostUsd).toBe(0.1);
    expect(model.estimatedCostUsd).toBeNull();
    expect(model.costUsd).toBeNull();
    expect(model.costOriginCounts).toEqual({ reported: 1 });
    expect(
      summarizeAgentCostEvents(
        model.attempts[0]?.steps.flatMap((step) => step.costEvents) ?? [],
        model.ownerControlJobAttempt,
      ),
    ).toMatchObject({
      costUnknown: true,
      costCompleteness: "partial_unknown",
    });
  });

  it("does not promote an event with no identity into an amount", () => {
    const model = normalizeAgentPipeline({
      owner_control_job_attempt: 1,
      attempts: [
        {
          attempt: 1,
          steps: [
            {
              agent: "model_variant",
              action: "done",
              cost_events: [
                {
                  cost_origin: "reported",
                  amount: "0.25",
                  cost_usd: 0.25,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 1,
                  pre_admission_attempt_id: null,
                },
                {
                  event_id: "provider:known-subtotal",
                  cost_origin: "reported",
                  amount: "0.10",
                  cost_usd: 0.1,
                  settlement_status: "committed",
                  durability: "ledger",
                  control_job_attempt: 1,
                  pre_admission_attempt_id: null,
                },
              ],
            },
          ],
        },
      ],
    });

    expect(model.reportedCostUsd).toBe(0.1);
    expect(model.costOriginCounts).toEqual({ reported: 1 });
    expect(model.costUsd).toBeNull();
    expect(
      summarizeAgentCostEvents(
        model.attempts[0]?.steps.flatMap((step) => step.costEvents) ?? [],
        model.ownerControlJobAttempt,
      ),
    ).toMatchObject({
      reportedCostUsd: 0.1,
      costUnknown: true,
      costCompleteness: "partial_unknown",
    });
  });
  // Compact wire fixtures are direct cost-field projections from actual AgentPipelineView.model_dump(mode='json') outputs under verified owner context. They retain producer zero subtotals and event multiplicity; unrelated API fields are omitted. Probe stdout@24b8f99890780d1a6d850097d185a216138de6d8df51aad0ddbeb41f3a972629; runtime.py@75a74fb0280ad2671c955dc3001483d086bb448a5a0320f0435a3c73bb98ca92. This exercises the validated Core model producer, not the HTTP route.
  const coreProducerProjectionFixtures = [
    {
      name: "reported_only",
      wire: {
        owner_control_job_attempt: 2,
        cost_usd: 0.25,
        reported_cost_usd: 0.25,
        estimated_cost_usd: 0.0,
        unattributed_cost_scalars: [],
        attempts: [
          {
            attempt: 1,
            cost_usd: 0.25,
            reported_cost_usd: 0.25,
            estimated_cost_usd: 0.0,
            unattributed_cost_scalars: [],
            steps: [
              {
                attempt: 1,
                agent: "model_variant",
                action: "reported_only-0",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.25,
                reported_cost_usd: 0.25,
                estimated_cost_usd: 0.0,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:reported",
                    origin_event_id: null,
                    cost_origin: "reported",
                    amount: "0.25",
                    cost_usd: 0.25,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:reported"],
                    payload_digest: "sha256:provider:reported",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
            ],
          },
        ],
      },
      display: {
        costUsd: 0.25,
        reportedCostUsd: 0.25,
        estimatedCostUsd: null,
        costUnknown: false,
        costCompleteness: "complete",
      },
    },
    {
      name: "estimated_only",
      wire: {
        owner_control_job_attempt: 2,
        cost_usd: 0.05,
        reported_cost_usd: 0.0,
        estimated_cost_usd: 0.05,
        unattributed_cost_scalars: [],
        attempts: [
          {
            attempt: 1,
            cost_usd: 0.05,
            reported_cost_usd: 0.0,
            estimated_cost_usd: 0.05,
            unattributed_cost_scalars: [],
            steps: [
              {
                attempt: 1,
                agent: "model_variant",
                action: "estimated_only-0",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.05,
                reported_cost_usd: 0.0,
                estimated_cost_usd: 0.05,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:estimated",
                    origin_event_id: null,
                    cost_origin: "estimated",
                    amount: "0.05",
                    cost_usd: 0.05,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:estimated"],
                    payload_digest: "sha256:provider:estimated",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
            ],
          },
        ],
      },
      display: {
        costUsd: null,
        reportedCostUsd: null,
        estimatedCostUsd: 0.05,
        costUnknown: false,
        costCompleteness: "complete",
      },
    },
    {
      name: "mixed",
      wire: {
        owner_control_job_attempt: 2,
        cost_usd: 0.3,
        reported_cost_usd: 0.25,
        estimated_cost_usd: 0.05,
        unattributed_cost_scalars: [],
        attempts: [
          {
            attempt: 1,
            cost_usd: 0.3,
            reported_cost_usd: 0.25,
            estimated_cost_usd: 0.05,
            unattributed_cost_scalars: [],
            steps: [
              {
                attempt: 1,
                agent: "model_variant",
                action: "mixed-0",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.3,
                reported_cost_usd: 0.25,
                estimated_cost_usd: 0.05,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:reported",
                    origin_event_id: null,
                    cost_origin: "reported",
                    amount: "0.25",
                    cost_usd: 0.25,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:reported"],
                    payload_digest: "sha256:provider:reported",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                  {
                    event_id: "provider:estimated",
                    origin_event_id: null,
                    cost_origin: "estimated",
                    amount: "0.05",
                    cost_usd: 0.05,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:estimated"],
                    payload_digest: "sha256:provider:estimated",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
            ],
          },
        ],
      },
      display: {
        costUsd: null,
        reportedCostUsd: 0.25,
        estimatedCostUsd: 0.05,
        costUnknown: false,
        costCompleteness: "complete",
      },
    },
    {
      name: "reuse_only",
      wire: {
        owner_control_job_attempt: 2,
        cost_usd: 0.0,
        reported_cost_usd: 0.0,
        estimated_cost_usd: 0.0,
        unattributed_cost_scalars: [],
        attempts: [
          {
            attempt: 1,
            cost_usd: 0.0,
            reported_cost_usd: 0.0,
            estimated_cost_usd: 0.0,
            unattributed_cost_scalars: [],
            steps: [
              {
                attempt: 1,
                agent: "model_variant",
                action: "reuse_only-0",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.0,
                reported_cost_usd: 0.0,
                estimated_cost_usd: 0.0,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:reuse",
                    origin_event_id: "provider:origin",
                    cost_origin: "reuse",
                    amount: "0",
                    cost_usd: 0.0,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:reuse"],
                    payload_digest: "sha256:provider:reuse",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
            ],
          },
        ],
      },
      display: {
        costUsd: null,
        reportedCostUsd: null,
        estimatedCostUsd: null,
        costUnknown: true,
        costCompleteness: "unknown",
      },
    },
    {
      name: "unknown_only",
      wire: {
        owner_control_job_attempt: 2,
        cost_usd: null,
        reported_cost_usd: 0.0,
        estimated_cost_usd: 0.0,
        unattributed_cost_scalars: [],
        attempts: [
          {
            attempt: 1,
            cost_usd: null,
            reported_cost_usd: 0.0,
            estimated_cost_usd: 0.0,
            unattributed_cost_scalars: [],
            steps: [
              {
                attempt: 1,
                agent: "model_variant",
                action: "unknown_only-0",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: null,
                reported_cost_usd: 0.0,
                estimated_cost_usd: 0.0,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:unknown",
                    origin_event_id: null,
                    cost_origin: "unknown",
                    amount: null,
                    cost_usd: null,
                    settlement_status: "unknown",
                    durability: "ledger",
                    receipts: ["provider:unknown"],
                    payload_digest: "sha256:provider:unknown",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
            ],
          },
        ],
      },
      display: {
        costUsd: null,
        reportedCostUsd: null,
        estimatedCostUsd: null,
        costUnknown: true,
        costCompleteness: "unknown",
      },
    },
    {
      name: "pending_reported",
      wire: {
        owner_control_job_attempt: 2,
        cost_usd: null,
        reported_cost_usd: 0.05,
        estimated_cost_usd: 0.0,
        unattributed_cost_scalars: [],
        attempts: [
          {
            attempt: 1,
            cost_usd: null,
            reported_cost_usd: 0.05,
            estimated_cost_usd: 0.0,
            unattributed_cost_scalars: [],
            steps: [
              {
                attempt: 1,
                agent: "model_variant",
                action: "pending_reported-0",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: null,
                reported_cost_usd: 0.05,
                estimated_cost_usd: 0.0,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:pending",
                    origin_event_id: null,
                    cost_origin: "reported",
                    amount: "0.05",
                    cost_usd: 0.05,
                    settlement_status: "pending",
                    durability: "ledger",
                    receipts: ["provider:pending"],
                    payload_digest: "sha256:provider:pending",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
            ],
          },
        ],
      },
      display: {
        costUsd: null,
        reportedCostUsd: null,
        estimatedCostUsd: null,
        costUnknown: true,
        costCompleteness: "unknown",
      },
    },
    {
      name: "zero_reported",
      wire: {
        owner_control_job_attempt: 2,
        cost_usd: 0.0,
        reported_cost_usd: 0.0,
        estimated_cost_usd: 0.0,
        unattributed_cost_scalars: [],
        attempts: [
          {
            attempt: 1,
            cost_usd: 0.0,
            reported_cost_usd: 0.0,
            estimated_cost_usd: 0.0,
            unattributed_cost_scalars: [],
            steps: [
              {
                attempt: 1,
                agent: "model_variant",
                action: "zero_reported-0",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.0,
                reported_cost_usd: 0.0,
                estimated_cost_usd: 0.0,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:zero",
                    origin_event_id: null,
                    cost_origin: "reported",
                    amount: "0",
                    cost_usd: 0.0,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:zero"],
                    payload_digest: "sha256:provider:zero",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
            ],
          },
        ],
      },
      display: {
        costUsd: 0.0,
        reportedCostUsd: 0.0,
        estimatedCostUsd: null,
        costUnknown: false,
        costCompleteness: "complete",
      },
    },
    {
      name: "identical_event_repeated_across_steps",
      wire: {
        owner_control_job_attempt: 2,
        cost_usd: 0.5,
        reported_cost_usd: 0.5,
        estimated_cost_usd: 0.0,
        unattributed_cost_scalars: [],
        attempts: [
          {
            attempt: 1,
            cost_usd: 0.5,
            reported_cost_usd: 0.5,
            estimated_cost_usd: 0.0,
            unattributed_cost_scalars: [],
            steps: [
              {
                attempt: 1,
                agent: "model_variant",
                action: "identical_event_repeated_across_steps-0",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.25,
                reported_cost_usd: 0.25,
                estimated_cost_usd: 0.0,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:reported",
                    origin_event_id: null,
                    cost_origin: "reported",
                    amount: "0.25",
                    cost_usd: 0.25,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:reported"],
                    payload_digest: "sha256:provider:reported",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
              {
                attempt: 1,
                agent: "model_variant",
                action: "identical_event_repeated_across_steps-1",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.25,
                reported_cost_usd: 0.25,
                estimated_cost_usd: 0.0,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:reported",
                    origin_event_id: null,
                    cost_origin: "reported",
                    amount: "0.25",
                    cost_usd: 0.25,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:reported"],
                    payload_digest: "sha256:provider:reported",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
            ],
          },
        ],
      },
      display: {
        costUsd: 0.25,
        reportedCostUsd: 0.25,
        estimatedCostUsd: null,
        costUnknown: false,
        costCompleteness: "complete",
      },
    },
    {
      name: "conflicting_identity_across_steps",
      wire: {
        owner_control_job_attempt: 2,
        cost_usd: 0.4,
        reported_cost_usd: 0.35,
        estimated_cost_usd: 0.05,
        unattributed_cost_scalars: [],
        attempts: [
          {
            attempt: 1,
            cost_usd: 0.4,
            reported_cost_usd: 0.35,
            estimated_cost_usd: 0.05,
            unattributed_cost_scalars: [],
            steps: [
              {
                attempt: 1,
                agent: "model_variant",
                action: "conflicting_identity_across_steps-0",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.25,
                reported_cost_usd: 0.25,
                estimated_cost_usd: 0.0,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:conflict",
                    origin_event_id: null,
                    cost_origin: "reported",
                    amount: "0.25",
                    cost_usd: 0.25,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:conflict"],
                    payload_digest: "sha256:conflict-a",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
              {
                attempt: 1,
                agent: "model_variant",
                action: "conflicting_identity_across_steps-1",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.05,
                reported_cost_usd: 0.0,
                estimated_cost_usd: 0.05,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:conflict",
                    origin_event_id: null,
                    cost_origin: "estimated",
                    amount: "0.05",
                    cost_usd: 0.05,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:conflict"],
                    payload_digest: "sha256:conflict-b",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
              {
                attempt: 1,
                agent: "model_variant",
                action: "conflicting_identity_across_steps-2",
                model: "provider-model",
                provider: "provider-x",
                model_variant_id: "shared-v",
                cost_usd: 0.1,
                reported_cost_usd: 0.1,
                estimated_cost_usd: 0.0,
                unattributed_cost_scalars: [],
                cost_events: [
                  {
                    event_id: "provider:known",
                    origin_event_id: null,
                    cost_origin: "reported",
                    amount: "0.10",
                    cost_usd: 0.1,
                    settlement_status: "committed",
                    durability: "ledger",
                    receipts: ["provider:known"],
                    payload_digest: "sha256:provider:known",
                    model: "provider-model",
                    provider: "provider-x",
                    control_job_attempt: 2,
                    pre_admission_attempt_id: null,
                  },
                ],
              },
            ],
          },
        ],
      },
      display: {
        costUsd: null,
        reportedCostUsd: 0.1,
        estimatedCostUsd: null,
        costUnknown: true,
        costCompleteness: "partial_unknown",
      },
    },
  ] as const;

  it.each(coreProducerProjectionFixtures)(
    "reconciles $name summary scalars against Core producer output without changing display semantics",
    (fixture) => {
      const model = normalizeAgentPipeline(fixture.wire);
      const attempt = model.attempts[0];
      const events = model.attempts.flatMap((item) =>
        item.steps.flatMap((step) => step.costEvents),
      );

      expect(model.unattributedCostScalars).toEqual([]);
      expect(attempt?.unattributedCostScalars).toEqual([]);
      expect(
        attempt?.steps.map((step) => step.unattributedCostScalars),
      ).toEqual(attempt?.steps.map(() => []));
      expect(model).toMatchObject({
        costUsd: fixture.display.costUsd,
        reportedCostUsd: fixture.display.reportedCostUsd,
        estimatedCostUsd: fixture.display.estimatedCostUsd,
        attempts: [
          {
            costUsd: fixture.display.costUsd,
            reportedCostUsd: fixture.display.reportedCostUsd,
            estimatedCostUsd: fixture.display.estimatedCostUsd,
          },
        ],
      });
      expect(
        summarizeAgentCostEvents(events, model.ownerControlJobAttempt),
      ).toMatchObject(fixture.display);
    },
  );

  it("retains a producer scalar that no longer matches the source event projection", () => {
    const reported = coreProducerProjectionFixtures.find(
      (fixture) => fixture.name === "reported_only",
    );
    expect(reported).toBeDefined();
    const model = normalizeAgentPipeline({
      ...reported!.wire,
      estimated_cost_usd: 0.01,
    });

    expect(model.unattributedCostScalars).toEqual([
      expect.objectContaining({
        sourceField: "estimated_cost_usd",
        claimedValueUsd: 0.01,
        sourceKind: "pipeline_summary",
        scope: "not_established",
      }),
    ]);
  });
});
