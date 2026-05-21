import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "@/test/render";

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
  beforeEach(() => {
    normalizeAgentPipelineMock.mockReset();
    normalizeWorkflowMock.mockReset();
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
      attempts: [
        {
          attempt: 1,
          durationMs: 2_000,
          finishedAt: "2026-03-10T10:10:00Z",
          startedAt: "2026-03-10T10:09:00Z",
          status: "ok",
          steps: [
            {
              action: "draft",
              actionLabel: "Draft plan",
              agent: "planner",
              agentLabel: "Planner",
              completionTokens: 54,
              costUsd: 0.12,
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
          verdict: "APPROVE",
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
        verdict: "APPROVE",
      },
      hasPromptData: true,
      iterationLifecycle: {
        iteration: 2,
        state: "running",
        stopReason: "budget_cap",
      },
      latestVerdict: "APPROVE",
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
            status: "over_budget",
          },
          {
            budgetMs: 30_000,
            category: "llm",
            durationMs: 12_000,
            phase: "llm.total",
            status: "within_budget",
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
      totalAttempts: 1,
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
    expect(screen.getByText(/Grounded in evidence/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Draft plan/ }));

    expect(screen.getByText("Drafted a grounded plan")).toBeInTheDocument();
    expect(screen.getByText("Plan prompt")).toBeInTheDocument();
    expect(screen.getByText("Plan response")).toBeInTheDocument();
    expect(
      screen.getByText("panels.agentPipeline.rawDetails"),
    ).toBeInTheDocument();
  });

  it("renders an empty agent pipeline state when attempts are unavailable", () => {
    normalizeAgentPipelineMock.mockReturnValue({
      attempts: [],
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
      totalAttempts: 0,
    });

    renderWithProviders(<AgentPipelinePanel payload={null} />);

    expect(
      screen.getByText("panels.agentPipeline.unavailableTitle"),
    ).toBeInTheDocument();
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
});
