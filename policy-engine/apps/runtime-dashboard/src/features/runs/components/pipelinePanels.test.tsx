import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "@/test/render";
import { createPerformanceBudgetDisplayState } from "@/shared/lib/domain/agents";

const { normalizeAgentPipelineMock, normalizeWorkflowMock } = vi.hoisted(
  () => ({
    normalizeAgentPipelineMock: vi.fn(),
    normalizeWorkflowMock: vi.fn(),
  }),
);

vi.mock("@/shared/lib/domain/agents", async () => {
  const actual = await vi.importActual<
    typeof import("@/shared/lib/domain/agents")
  >("@/shared/lib/domain/agents");
  return {
    ...actual,
    normalizeAgentPipeline: (...args: unknown[]) =>
      normalizeAgentPipelineMock(...args),
  };
});

vi.mock("@/shared/lib/domain/workflow", async () => {
  const actual = await vi.importActual<
    typeof import("@/shared/lib/domain/workflow")
  >("@/shared/lib/domain/workflow");
  return {
    ...actual,
    normalizeWorkflow: (...args: unknown[]) => normalizeWorkflowMock(...args),
  };
});

vi.mock("@/shared/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<
    typeof import("@/shared/i18n/LocaleProvider")
  >("@/shared/i18n/LocaleProvider");
  return {
    ...actual,
    useI18n: () => ({
      label: (
        _namespace: string,
        value: string | null | undefined,
        fallback: string,
      ) => fallback ?? value ?? "",
      t: (key: string, payload?: Record<string, unknown>) =>
        payload ? `${key}:${JSON.stringify(payload)}` : key,
    }),
  };
});

import AgentPipelinePanel from "@/features/runs/components/AgentPipelinePanel";
import GovernanceReport from "@/features/runs/components/GovernanceReport";
import WorkflowDagPanel from "@/features/runs/components/WorkflowDagPanel";

describe("pipeline surfaces", () => {
  const containerWithText = (role: "listitem" | "group", text: string) => {
    const matches = screen
      .getAllByRole(role)
      .filter((candidate) => within(candidate).queryByText(text) !== null);
    if (matches.length !== 1) {
      throw new Error("expected exactly one " + role + " containing " + text);
    }
    return matches[0];
  };

  const variantRow = (variantId: string) =>
    screen.getByRole("group", {
      name: "panels.agentPipeline.variant: " + variantId,
    });

  const costBreakdownIn = (row: HTMLElement) =>
    within(row).getByRole("group", {
      name: "panels.agentPipeline.cost",
    });

  beforeEach(() => {
    normalizeAgentPipelineMock.mockReset();
    normalizeWorkflowMock.mockReset();
  });

  it("workflow DAG uses generated node status and neutral unknown", async () => {
    const actual = await vi.importActual<
      typeof import("@/shared/lib/domain/workflow")
    >("@/shared/lib/domain/workflow");
    normalizeWorkflowMock.mockImplementation(actual.normalizeWorkflow);

    renderWithProviders(
      <WorkflowDagPanel
        payload={{
          nodes: [
            {
              alias: "mystery_node",
              depth: 0,
              duration_ms: 10,
              heat: 0,
              status: "running",
            },
          ],
        }}
        runId="run-unknown"
      />,
    );

    const unknownBadges = screen.getAllByText("unknown");
    expect(unknownBadges).toHaveLength(2);
    for (const badge of unknownBadges) {
      expect(badge).toHaveClass("bg-white/65", "text-muted");
    }
  });

  it("renders workflow DAG summaries, notes, edges, and debug links", () => {
    normalizeWorkflowMock.mockReturnValue({
      edges: [{ fromAlias: "prepare", toAlias: "score" }],
      nodes: [
        {
          alias: "prepare",
          dependsOn: [],
          depth: 0,
          durationMs: 1_200,
          errorCode: null,
          heat: 0.2,
          label: "Prepare evidence",
          nodeId: "node-1",
          status: "ok",
        },
        {
          alias: "score",
          dependsOn: ["prepare"],
          depth: 1,
          durationMs: 2_400,
          errorCode: "E_TIMEOUT",
          heat: 0.95,
          label: "Score outcomes",
          nodeId: "node-2",
          status: "fail",
        },
      ],
      notes: ["Escalated due to timeout"],
      summary: {
        criticalPathDurationMs: 3_600,
        edgeCount: 1,
        errorPolicy: "strict",
        nodeCount: 2,
        status: "fail",
        workflowId: "wf-1",
      },
    });

    renderWithProviders(<WorkflowDagPanel payload={{}} runId="run-1" />);

    expect(screen.getByText("wf-1")).toBeInTheDocument();
    expect(screen.getByText("Escalated due to timeout")).toBeInTheDocument();
    expect(screen.getAllByText("Prepare evidence")).toHaveLength(2);
    expect(screen.getByText("E_TIMEOUT")).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: "panels.workflow.openDebug" }),
    ).toHaveLength(2);
  });

  it("renders workflow empty states when the DAG has no nodes", () => {
    normalizeWorkflowMock.mockReturnValue({
      edges: [],
      nodes: [],
      notes: [],
      summary: {
        criticalPathDurationMs: 0,
        edgeCount: 0,
        errorPolicy: null,
        nodeCount: 0,
        status: null,
        workflowId: null,
      },
    });

    renderWithProviders(<WorkflowDagPanel payload={null} runId="run-1" />);

    expect(screen.getByText("panels.workflow.emptyTitle")).toBeInTheDocument();
  });

  it("renders agent telemetry, model summaries, and selected step details", async () => {
    normalizeAgentPipelineMock.mockReturnValue({
      ownerControlJobAttempt: null,
      attempts: [
        {
          attempt: 1,
          costOriginCounts: { unknown: 1 },
          costUsd: null,
          durationMs: 2_000,
          estimatedCostUsd: 0,
          finishedAt: "2026-03-10T10:10:00Z",
          startedAt: "2026-03-10T10:09:00Z",
          reportedCostUsd: 0,
          settlementStatusCounts: { unknown: 1 },
          status: "ok",
          steps: [
            {
              action: "draft",
              actionLabel: "Draft plan",
              agent: "planner",
              agentLabel: "Planner",
              completionTokens: 54,
              costUsd: null,
              costUnknown: true,
              costEvents: [
                {
                  amount: null,
                  costOrigin: "unknown",
                  costUsd: null,
                  durability: "none",
                  eventId: "llm-provider:unknown",
                  model: "openai/gpt-5.4",
                  originEventId: null,
                  payloadDigest: "sha256:unknown",
                  provider: "OpenAI",
                  receipts: [],
                  settlementStatus: "unknown",
                },
              ],
              details: { lane: "fastlane" },
              latencyMs: 180,
              model: "openai/gpt-5.4",
              modelVariantId: "gpt-5.4-v1",
              prompt: "Plan prompt",
              promptTokens: 120,
              provider: "OpenAI",
              response: "Plan response",
              status: "ok",
              summary: "Drafted a grounded plan",
              timestamp: "2026-03-10T10:09:15Z",
              totalTokens: 174,
            },
          ],
          verdict: "future-owner-grade",
        },
      ],
      evaluator: {
        reasons: ["Grounded in evidence"],
        scores: {
          budgetScore: 0.62,
          constraintsScore: 0.94,
          dataQualityScore: 0.81,
          kpiScore: 0.88,
          totalScore: 0.9,
        },
        verdict: "future-owner-grade",
      },
      hasPromptData: true,
      costOriginCounts: { unknown: 1 },
      costUsd: null,
      estimatedCostUsd: 0,
      iterationLifecycle: {
        iteration: 2,
        state: "running",
        stopReason: "budget_cap",
      },
      latestVerdict: "future-owner-grade",
      notes: ["Fallback lane engaged"],
      performanceSummary: {
        llmLatencyMs: 125_000,
        overBudgetCount: 1,
        phaseBudgets: [
          {
            budgetMs: 10_000,
            category: "retrieval",
            durationMs: 15_000,
            phase: "retrieval.materialize",
            status: createPerformanceBudgetDisplayState("over_budget"),
          },
          {
            budgetMs: 30_000,
            category: "llm",
            durationMs: 12_000,
            phase: "llm.total",
            status: createPerformanceBudgetDisplayState("within_budget"),
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
            code: "missing_snapshot",
            message: "Attach the latest snapshot.",
            replanningHints: ["Bind a fresh dataset"],
            severity: "warning",
          },
        ],
        readyToRun: false,
      },
      reproducibility: {
        planHash: "plan-hash-1",
        seed: 42,
      },
      retrieval: {
        candidatesFiltered: 2,
        candidatesPromoted: 1,
        laneUsed: "fastlane",
        localIndexDocsTotal: 48,
        localIndexSizeBytes: 2_048,
        metadataDocsFetched: 6,
        mode: "hybrid",
        notes: ["Promotion lane fallback"],
        phases: [
          {
            candidatesSelected: 3,
            candidatesTotal: 8,
            docsFetched: 6,
            durationMs: 900,
            lane: "fastlane",
            phase: "discover",
          },
        ],
      },
      source: "runtime",
      reportedCostUsd: 0,
      settlementStatusCounts: { unknown: 1 },
      totalAttempts: 1,
      unattributedCostEvents: [],
      unattributedCostScalars: [],
    });

    const user = userEvent.setup();
    renderWithProviders(<AgentPipelinePanel payload={{}} />);

    expect(screen.getByText("Fallback lane engaged")).toBeInTheDocument();
    expect(
      screen.getByText("panels.agentPipeline.performanceBudget"),
    ).toBeInTheDocument();
    expect(
      screen.getByText('panels.agentPipeline.overBudget:{"count":"1"}'),
    ).toBeInTheDocument();
    expect(screen.getByText("retrieval.materialize")).toBeInTheDocument();
    expect(screen.getByText("Promotion lane fallback")).toBeInTheDocument();
    expect(screen.getByText("Draft plan")).toBeInTheDocument();
    expect(
      screen.getByText("panels.agentPipeline.costUnknown"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Grounded in evidence/)).toBeInTheDocument();
    const ownerStatuses = screen.getAllByText("ok");
    expect(ownerStatuses).toHaveLength(2);
    for (const ownerStatus of ownerStatuses) {
      expect(ownerStatus).toHaveAttribute("data-kind", "neutral");
      expect(ownerStatus).toHaveAttribute("data-owner-status", "ok");
    }
    const ownerGrades = screen.getAllByText("future-owner-grade");
    expect(ownerGrades).toHaveLength(3);
    for (const ownerGrade of ownerGrades) {
      expect(ownerGrade).toHaveAttribute(
        "data-decision-grade-presentation",
        "unrecognized",
      );
    }

    await user.click(screen.getByRole("button", { name: /Draft plan/ }));

    expect(screen.getByText("Drafted a grounded plan")).toBeInTheDocument();
    expect(screen.getByText("Plan prompt")).toBeInTheDocument();
    expect(screen.getByText("Plan response")).toBeInTheDocument();
    expect(screen.getByText("llm-provider:unknown")).toBeInTheDocument();
    expect(
      screen.getByText("panels.agentPipeline.rawDetails"),
    ).toBeInTheDocument();
  });

  it("renders an empty agent pipeline state when attempts are unavailable", () => {
    normalizeAgentPipelineMock.mockReturnValue({
      ownerControlJobAttempt: null,
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
      retrieval: null,
      source: null,
      reportedCostUsd: null,
      settlementStatusCounts: {},
      totalAttempts: 0,
      unattributedCostEvents: [],
      unattributedCostScalars: [],
    });

    renderWithProviders(<AgentPipelinePanel payload={null} />);

    expect(
      screen.getByText("panels.agentPipeline.unavailableTitle"),
    ).toBeInTheDocument();
  });

  it("uses the verified owner attempt in the actual route-shaped model comparison", async () => {
    const actual = await vi.importActual<
      typeof import("@/shared/lib/domain/agents")
    >("@/shared/lib/domain/agents");
    normalizeAgentPipelineMock.mockImplementation(
      actual.normalizeAgentPipeline,
    );
    const user = userEvent.setup();
    renderWithProviders(
      <AgentPipelinePanel
        payload={{
          owner_control_job_attempt: 2,
          attempts: [
            {
              // The producer step has ordinal 1 although the persisted owner is attempt 2.
              attempt: 1,
              steps: [
                {
                  action: "durable_ledger",
                  agent: "llm_producer_settlement",
                  attempt: 1,
                  details: {
                    nested: {
                      cost_usd: 0.73,
                      annotation: "diagnostic $9 only",
                    },
                  },
                  details_cost_scope: "not_established",
                  cost_events: [
                    {
                      amount: "0.12",
                      cost_origin: "reported",
                      control_job_attempt: 1,
                      cost_usd: 0.12,
                      durability: "ledger",
                      event_id: "same-label-old-attempt",
                      pre_admission_attempt_id: null,
                      receipts: ["same-label-old-attempt"],
                      settlement_status: "committed",
                    },
                    {
                      amount: "0.01",
                      cost_origin: "reported",
                      control_job_attempt: 2,
                      cost_usd: 0.01,
                      durability: "ledger",
                      event_id: "owner-attempt-ledger",
                      pre_admission_attempt_id: null,
                      receipts: ["owner-attempt-ledger"],
                      settlement_status: "committed",
                    },
                  ],
                },
                {
                  action: "legacy_scalar",
                  agent: "llm_producer_settlement",
                  attempt: 1,
                  cost_usd: 0.41,
                  model_variant_id: "legacy-scalar-variant",
                },
              ],
            },
            {
              attempt: 2,
              steps: [
                {
                  action: "completed",
                  agent: "model_variant",
                  attempt: 2,
                  model: "openai/gpt-5.4",
                  model_variant_id: "shared-owner-variant",
                  cost_events: [
                    {
                      amount: "0.02",
                      cost_origin: "reported",
                      control_job_attempt: 2,
                      cost_usd: 0.02,
                      durability: "ledger",
                      event_id: "owner-variant-a",
                      pre_admission_attempt_id: null,
                      receipts: ["owner-variant-a"],
                      settlement_status: "committed",
                    },
                  ],
                },
              ],
            },
            {
              attempt: 3,
              steps: [
                {
                  action: "completed",
                  agent: "model_variant",
                  attempt: 3,
                  model: "openai/gpt-5.4",
                  model_variant_id: "shared-owner-variant",
                  cost_events: [
                    {
                      amount: "0.03",
                      cost_origin: "reported",
                      control_job_attempt: 2,
                      cost_usd: 0.03,
                      durability: "ledger",
                      event_id: "owner-variant-b",
                      pre_admission_attempt_id: null,
                      receipts: ["owner-variant-b"],
                      settlement_status: "committed",
                    },
                  ],
                },
              ],
            },
          ],
        }}
      />,
    );

    expect(
      screen.getByText("panels.agentPipeline.unattributedCostScalars"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("step_summary.cost_usd", { exact: false }),
    ).toBeInTheDocument();
    expect(screen.getByText("shared-owner-variant")).toBeInTheDocument();
    expect(
      screen.getByText('panels.agentPipeline.ownerAttemptScope:{"attempt":2}'),
    ).toBeInTheDocument();
    expect(
      screen.getByText("panels.agentPipeline.reportedCost: $0.01"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("panels.agentPipeline.reportedCost: $0.05"),
    ).toBeInTheDocument();
    expect(screen.queryByText("$0.12")).not.toBeInTheDocument();
    expect(screen.queryByText("$0.41")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Durable ledger/i }));
    await user.click(screen.getByText("panels.agentPipeline.rawDetails"));
    const rawDetails = within(
      containerWithText("group", "panels.agentPipeline.rawDetails"),
    );
    expect(
      rawDetails.getByText("panels.agentPipeline.rawDetailsNotEstablished"),
    ).toBeInTheDocument();
    expect(rawDetails.getByText(/"cost_usd": 0\.73/u)).toBeInTheDocument();
    expect(rawDetails.getByText(/diagnostic \$9 only/u)).toBeInTheDocument();
    const currentEventRow = within(
      containerWithText("listitem", "owner-attempt-ledger"),
    );
    const priorEventRow = within(
      containerWithText("listitem", "same-label-old-attempt"),
    );
    expect(
      currentEventRow.getByText("$0.01", { exact: false }),
    ).toBeInTheDocument();
    expect(
      currentEventRow.getByText("panels.agentPipeline.controlJobAttempt: 2", {
        exact: false,
      }),
    ).toBeInTheDocument();
    expect(
      priorEventRow.getByText("panels.agentPipeline.costUnknown", {
        exact: false,
      }),
    ).toBeInTheDocument();
    expect(
      priorEventRow.getByText("panels.agentPipeline.eventCostNotAttributed", {
        exact: false,
      }),
    ).toBeInTheDocument();
    expect(priorEventRow.queryByText("0.12", { exact: false })).toBeNull();
  });

  it("shows costs as unassigned when the owner attempt is absent", async () => {
    const actual = await vi.importActual<
      typeof import("@/shared/lib/domain/agents")
    >("@/shared/lib/domain/agents");
    normalizeAgentPipelineMock.mockImplementation(
      actual.normalizeAgentPipeline,
    );
    const user = userEvent.setup();
    renderWithProviders(
      <AgentPipelinePanel
        payload={{
          cost_usd: 0.99,
          attempts: [
            {
              attempt: 2,
              cost_usd: 0.98,
              steps: [
                {
                  action: "durable_ledger",
                  agent: "model_variant",
                  attempt: 2,
                  cost_usd: 0.97,
                  model: "openai/gpt-5.4",
                  model_variant_id: "unbound-owner-variant",
                  cost_events: [
                    {
                      amount: "0.03",
                      cost_origin: "reported",
                      control_job_attempt: 2,
                      cost_usd: 0.03,
                      durability: "ledger",
                      event_id: "event-without-owner-binding",
                      pre_admission_attempt_id: null,
                      receipts: ["event-without-owner-binding"],
                      settlement_status: "committed",
                    },
                  ],
                },
              ],
            },
          ],
        }}
      />,
    );

    expect(
      screen.getByText("panels.agentPipeline.ownerAttemptUnknown"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("panels.agentPipeline.costUnknown"),
    ).toBeInTheDocument();
    expect(screen.queryByText("$0.03")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Durable ledger/i }));
    const eventRow = within(
      containerWithText("listitem", "event-without-owner-binding"),
    );
    expect(
      eventRow.getByText("panels.agentPipeline.costUnknown", { exact: false }),
    ).toBeInTheDocument();
    expect(
      eventRow.getByText("panels.agentPipeline.eventCostNotAttributed", {
        exact: false,
      }),
    ).toBeInTheDocument();
    expect(eventRow.queryByText("0.03", { exact: false })).toBeNull();
  });

  it("renders governance summaries, issues, and linked artifacts", () => {
    renderWithProviders(
      <GovernanceReport
        data={
          {
            contract_warnings: ["contract drift"],
            fallback_from_decision_packet: true,
            issue_summary: {
              blocker_count: 1,
              info_count: 0,
              warning_count: 1,
            },
            issues: [
              {
                code: "LEGAL-1",
                duration_ms: 18,
                message: "Policy conflict detected",
                pass_id: "pass-1",
                path: "policy/legal",
                raw: { rule: "no-harm" },
                severity: "blocker",
              },
            ],
            legal_executed: false,
            links: {
              decision_packet: { artifact_id: "artifact-1" },
            },
            notes: ["Needs manual review"],
            report_kind: "runtime_governance",
            report_ref: { artifact_id: "report-1" },
            report_schema_version: "2026-03",
            transport_summary: {
              identification_engine: "atlas",
              status: "identified",
            },
            validation_trace: {
              stage: "evaluator",
            },
            verdict: "REJECT",
          } as never
        }
      />,
    );

    expect(screen.getByText(/Needs manual review/)).toBeInTheDocument();
    expect(screen.getByText("contract drift")).toBeInTheDocument();
    expect(screen.getByText("LEGAL-1")).toBeInTheDocument();
    expect(screen.getByText("artifact-1")).toBeInTheDocument();
    expect(screen.getByText(/report-1/)).toBeInTheDocument();
  });

  it("renders the empty governance issue state", () => {
    renderWithProviders(
      <GovernanceReport
        data={
          {
            contract_warnings: [],
            fallback_from_decision_packet: false,
            issue_summary: null,
            issues: [],
            legal_executed: null,
            links: {},
            notes: [],
            report_kind: null,
            report_ref: null,
            report_schema_version: null,
            transport_summary: null,
            validation_trace: null,
            verdict: "APPROVE",
          } as never
        }
      />,
    );

    expect(
      screen.getByText("panels.governance.emptyIssues"),
    ).toBeInTheDocument();
  });

  it("renders model comparison cost by origin and keeps unknown or reused spend open", async () => {
    const actual = await vi.importActual<
      typeof import("@/shared/lib/domain/agents")
    >("@/shared/lib/domain/agents");
    normalizeAgentPipelineMock.mockImplementation(
      actual.normalizeAgentPipeline,
    );
    renderWithProviders(
      <AgentPipelinePanel
        payload={{
          owner_control_job_attempt: 1,
          attempts: [
            {
              attempt: 1,
              steps: [
                {
                  agent: "model_variant",
                  action: "completed",
                  timestamp: "2026-10-23T00:00:01Z",
                  model: "model-a",
                  model_variant_id: "estimate-v1",
                  cost_events: [
                    {
                      event_id: "estimate:one",
                      cost_origin: "estimated",
                      amount: "0.05",
                      cost_usd: 0.05,
                      settlement_status: "committed",
                      durability: "ledger",
                      control_job_attempt: 1,
                    },
                  ],
                },
                {
                  agent: "model_variant",
                  action: "completed",
                  timestamp: "2026-10-23T00:00:02Z",
                  model: "model-b",
                  model_variant_id: "mixed-v1",
                  cost_events: [
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
                      event_id: "estimate:two",
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
                  ],
                },
                {
                  agent: "model_variant",
                  action: "completed",
                  timestamp: "2026-10-23T00:00:03Z",
                  model: "model-c",
                  model_variant_id: "reuse-v1",
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
        }}
      />,
    );

    const estimateRow = variantRow("estimate-v1");
    const mixedRow = variantRow("mixed-v1");
    const reuseRow = variantRow("reuse-v1");
    expect(costBreakdownIn(estimateRow)).toHaveAttribute(
      "data-cost-completeness",
      "complete",
    );
    expect(estimateRow).toHaveTextContent(
      "panels.agentPipeline.estimatedCost: $0.05",
    );
    expect(costBreakdownIn(mixedRow)).toHaveAttribute(
      "data-cost-completeness",
      "partial_unknown",
    );
    expect(mixedRow).toHaveTextContent(
      "panels.agentPipeline.reportedCost: $0.02",
    );
    expect(mixedRow).toHaveTextContent(
      "panels.agentPipeline.estimatedCost: $0.03",
    );
    expect(mixedRow).toHaveTextContent("panels.agentPipeline.costUnknown");
    expect(costBreakdownIn(reuseRow)).toHaveAttribute(
      "data-cost-completeness",
      "unknown",
    );
    expect(reuseRow).toHaveTextContent("panels.agentPipeline.reuseEvents: 1");
    expect(reuseRow).toHaveTextContent("panels.agentPipeline.costUnknown");
    expect(reuseRow).not.toHaveTextContent("$0.09");
  });

  it("keeps the current owner model subtotal complete when same-key stale and unowned non-ledger rows are present", async () => {
    const actual = await vi.importActual<
      typeof import("@/shared/lib/domain/agents")
    >("@/shared/lib/domain/agents");
    normalizeAgentPipelineMock.mockImplementation(
      actual.normalizeAgentPipeline,
    );
    const currentOwnerEvent = {
      event_id: "provider:owner-current",
      cost_origin: "reported",
      amount: "0.25",
      cost_usd: 0.25,
      settlement_status: "committed",
      durability: "ledger",
      control_job_attempt: 2,
      pre_admission_attempt_id: null,
      payload_digest: "sha256:owner-current",
    };
    const staleSameIdentity = {
      ...currentOwnerEvent,
      amount: "9.00",
      cost_usd: 9,
      control_job_attempt: 1,
      payload_digest: "sha256:stale-owner",
    };
    const unownedMemoryClaim = {
      event_id: "provider:unowned-memory",
      cost_origin: "unknown",
      amount: null,
      cost_usd: null,
      settlement_status: "unknown",
      durability: "memory",
      control_job_attempt: null,
      pre_admission_attempt_id: null,
    };
    renderWithProviders(
      <AgentPipelinePanel
        payload={{
          owner_control_job_attempt: 2,
          attempts: [
            {
              attempt: 1,
              steps: [
                {
                  agent: "model_variant",
                  action: "stale attempt same key",
                  model: "shared",
                  model_variant_id: "shared-v",
                  cost_events: [staleSameIdentity],
                },
              ],
            },
            {
              attempt: 2,
              steps: [
                {
                  agent: "model_variant",
                  action: "current owner projection",
                  model: "shared",
                  model_variant_id: "shared-v",
                  cost_usd: 0.25,
                  reported_cost_usd: 0.25,
                  cost_events: [currentOwnerEvent],
                },
                {
                  agent: "model_variant",
                  action: "unowned memory observation",
                  model: "shared",
                  model_variant_id: "shared-v",
                  cost_events: [unownedMemoryClaim],
                },
                {
                  agent: "model_variant",
                  action: "unscoped legacy scalar",
                  model: "shared",
                  model_variant_id: "shared-v",
                  cost_usd: 0.8,
                },
              ],
            },
          ],
        }}
      />,
    );

    const sharedRow = variantRow("shared-v");
    expect(costBreakdownIn(sharedRow)).toHaveAttribute(
      "data-cost-completeness",
      "complete",
    );
    expect(sharedRow).toHaveTextContent(
      "panels.agentPipeline.reportedCost: $0.25",
    );
    expect(sharedRow).not.toHaveTextContent("panels.agentPipeline.costUnknown");
    expect(sharedRow).not.toHaveTextContent("$9.00");
    expect(
      screen.getByText("panels.agentPipeline.unattributedCostScalars"),
    ).toBeInTheDocument();
    expect(screen.getByText(/\$0\.80/)).toBeInTheDocument();
  });

  it("deduplicates one identity within a model and leaves cross-model attribution unresolved", async () => {
    const actual = await vi.importActual<
      typeof import("@/shared/lib/domain/agents")
    >("@/shared/lib/domain/agents");
    normalizeAgentPipelineMock.mockImplementation(
      actual.normalizeAgentPipeline,
    );
    const sharedWithinModel = {
      event_id: "provider:same-model",
      cost_origin: "reported",
      amount: "0.25",
      cost_usd: 0.25,
      settlement_status: "committed",
      durability: "ledger",
      control_job_attempt: 1,
      pre_admission_attempt_id: null,
      payload_digest: "sha256:same-model",
    };
    const staleAcrossBuckets = {
      ...sharedWithinModel,
      cost_usd: 9,
      amount: "9.00",
      control_job_attempt: 2,
      payload_digest: "sha256:stale",
    };
    const acrossModels = {
      event_id: "provider:ambiguous-model",
      cost_origin: "reported",
      amount: "0.25",
      cost_usd: 0.25,
      settlement_status: "committed",
      durability: "ledger",
      control_job_attempt: 1,
      pre_admission_attempt_id: null,
      payload_digest: "sha256:ambiguous-model",
    };
    renderWithProviders(
      <AgentPipelinePanel
        payload={{
          owner_control_job_attempt: 1,
          attempts: [
            {
              attempt: 1,
              steps: [
                {
                  agent: "model_variant",
                  action: "one",
                  model: "same",
                  model_variant_id: "same-v",
                  cost_events: [sharedWithinModel],
                },
                {
                  agent: "model_variant",
                  action: "duplicate",
                  model: "same",
                  model_variant_id: "same-v",
                  cost_events: [sharedWithinModel],
                },
                {
                  agent: "model_variant",
                  action: "stale duplicate in another bucket",
                  model: "stale",
                  model_variant_id: "stale-v",
                  cost_events: [staleAcrossBuckets],
                },
                {
                  agent: "model_variant",
                  action: "left",
                  model: "left",
                  model_variant_id: "left-v",
                  cost_events: [
                    acrossModels,
                    {
                      event_id: "provider:left-known",
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
                {
                  agent: "model_variant",
                  action: "right",
                  model: "right",
                  model_variant_id: "right-v",
                  cost_events: [
                    acrossModels,
                    {
                      event_id: "provider:right-known",
                      cost_origin: "reported",
                      amount: "0.20",
                      cost_usd: 0.2,
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
        }}
      />,
    );

    const sameRow = variantRow("same-v");
    const leftRow = variantRow("left-v");
    const rightRow = variantRow("right-v");
    expect(costBreakdownIn(sameRow)).toHaveAttribute(
      "data-cost-completeness",
      "complete",
    );
    expect(sameRow).toHaveTextContent(
      "panels.agentPipeline.reportedCost: $0.25",
    );
    expect(sameRow).not.toHaveTextContent("$0.50");
    for (const [row, subtotal] of [
      [leftRow, "$0.10"],
      [rightRow, "$0.20"],
    ] as const) {
      expect(costBreakdownIn(row)).toHaveAttribute(
        "data-cost-completeness",
        "partial_unknown",
      );
      expect(row).toHaveTextContent(
        "panels.agentPipeline.reportedCost: " + subtotal,
      );
      expect(row).toHaveTextContent("panels.agentPipeline.costUnknown");
      expect(row).not.toHaveTextContent("$0.25");
    }
  });
});
