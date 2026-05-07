import {
  buildNaturalLanguageLaunchRequest,
  buildWorkflowLaunchRequest,
  naturalLanguageLaunchSchema,
  workflowLaunchSchema,
} from "./forms";

describe("composer form schemas and mappers", () => {
  it("builds workflow payload from valid workflow form values", () => {
    const parsed = workflowLaunchSchema.parse({
      dataSourceType: "snapshot",
      dataSourceRef: "sha256:data",
      trinityRef: "sha256:trinity",
      policySpecRef: "",
      modelSpecRef: "",
      executionIntent: "Review blockers first",
      checkpointPolicy: "strict",
      expectedOutputs: [
        { kind: "decision_packet", description: "Decision packet" },
      ],
      governanceConstraints: [
        { scope: "legal", rule: "Surface blockers", severity: "blocker" },
      ],
      customParams: [{ key: "country", value: "UA" }],
    });

    expect(
      buildWorkflowLaunchRequest(parsed, {
        locale: "en",
        preflightEnabled: true,
        autoMaterializationEnabled: false,
      }),
    ).toMatchObject({
      mode: "workflow",
      checkpoint_policy: "strict",
      data_source: { data_snapshot_ref: "sha256:data" },
      trinity_bundle_ref: "sha256:trinity",
      params: {
        country: "UA",
        operator_intent: "Review blockers first",
      },
    });
  });

  it("builds nl payload with deduplicated model ids", () => {
    const parsed = naturalLanguageLaunchSchema.parse({
      nlRequest: "Assess affordability impacts",
      executionIntent: "Show blockers first",
      domainHint: "labor",
      selectedLlmModels: [
        "openai/gpt-5.4",
        "openai/gpt-5.4",
        "anthropic/claude",
      ],
      maxParallelModels: 4,
      runBudgetUsd: "25",
      perModelBudgetUsd: "",
      maxIterations: 3,
      checkpointPolicy: "lenient",
      nlDataSourceRef: "sha256:snapshot",
      expectedOutputs: [
        { kind: "decision_packet", description: "Decision packet" },
      ],
      governanceConstraints: [
        { scope: "budget", rule: "Stop if over budget", severity: "warning" },
      ],
    });

    expect(
      buildNaturalLanguageLaunchRequest(parsed, {
        locale: "uk",
        preflightEnabled: true,
        autoMaterializationEnabled: true,
        maxParallelConstraint: 3,
        maxIterationsConstraint: 5,
      }),
    ).toMatchObject({
      request: "Assess affordability impacts",
      llm_model: "openai/gpt-5.4",
      llm_models: ["openai/gpt-5.4", "anthropic/claude"],
      max_parallel_models: 2,
      run_budget_usd: 25,
      checkpoint_policy: "lenient",
      data_source: { data_snapshot_ref: "sha256:snapshot" },
    });
  });
});
