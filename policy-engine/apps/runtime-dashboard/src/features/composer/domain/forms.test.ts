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
      dataSourceProfileSha256: "",
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

  it("sends the selected full DataViewRequestRef and preserves legacy string calls", () => {
    const profile = `sha256:${"c".repeat(64)}`;
    const selected = workflowLaunchSchema.parse({
      dataSourceType: "view",
      dataSourceRef: "sha256:data-view-request",
      dataSourceProfileSha256: profile,
      trinityRef: "",
      policySpecRef: "",
      modelSpecRef: "",
      executionIntent: "Use the selected profile-bound request",
      checkpointPolicy: "strict",
      expectedOutputs: [
        { kind: "decision_packet", description: "Decision packet" },
      ],
      governanceConstraints: [
        { scope: "legal", rule: "Surface blockers", severity: "blocker" },
      ],
      customParams: [],
    });

    const typedBody = buildWorkflowLaunchRequest(selected, {
      locale: "en",
      preflightEnabled: true,
      autoMaterializationEnabled: false,
    });
    expect(typedBody.data_source).toEqual({
      data_view_request_ref: {
        artifact_id: "sha256:data-view-request",
        kind: "ir.data_view_request",
        media_type: "application/json",
        manifest_profile_sha256: profile,
      },
    });

    const { dataSourceProfileSha256: _selectedProfile, ...legacyValues } =
      selected;
    const legacy = workflowLaunchSchema.parse(legacyValues);
    expect(
      buildWorkflowLaunchRequest(legacy, {
        locale: "en",
        preflightEnabled: true,
        autoMaterializationEnabled: false,
      }).data_source,
    ).toEqual({ data_view_request_ref: "sha256:data-view-request" });
  });

  it("refuses malformed supplied profile selectors instead of dropping them", () => {
    const malformed = workflowLaunchSchema.safeParse({
      dataSourceType: "view",
      dataSourceRef: "sha256:data-view-request",
      dataSourceProfileSha256: "sha256:short",
      trinityRef: "",
      policySpecRef: "",
      modelSpecRef: "",
      executionIntent: "",
      checkpointPolicy: "strict",
      expectedOutputs: [
        { kind: "decision_packet", description: "Decision packet" },
      ],
      governanceConstraints: [
        { scope: "legal", rule: "Surface blockers", severity: "blocker" },
      ],
      customParams: [],
    });

    const malformedIssuePaths = malformed.success
      ? []
      : malformed.error.issues.map((issue) => issue.path.join("."));
    expect(malformed.success).toBe(false);
    expect(malformedIssuePaths).toContain("dataSourceProfileSha256");

    const misplaced = workflowLaunchSchema.safeParse({
      dataSourceType: "snapshot",
      dataSourceRef: "sha256:data-view-request",
      dataSourceProfileSha256: `sha256:${"f".repeat(64)}`,
      trinityRef: "",
      policySpecRef: "",
      modelSpecRef: "",
      executionIntent: "",
      checkpointPolicy: "strict",
      expectedOutputs: [
        { kind: "decision_packet", description: "Decision packet" },
      ],
      governanceConstraints: [
        { scope: "legal", rule: "Surface blockers", severity: "blocker" },
      ],
      customParams: [],
    });
    expect(misplaced.success).toBe(false);
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

  it("keeps predictive basis refs typed, exact, and all-or-none", () => {
    const digest = (char: string) => `sha256:${char.repeat(64)}`;
    const parsed = naturalLanguageLaunchSchema.parse({
      nlRequest: "Compare the selected policy candidate.",
      executionIntent: "",
      domainHint: "custom",
      selectedLlmModels: ["simulated-qwen"],
      maxParallelModels: 1,
      runBudgetUsd: "",
      perModelBudgetUsd: "",
      maxIterations: 1,
      checkpointPolicy: "strict",
      nlDataSourceRef: digest("a"),
      nlDataSourceProfileSha256: digest("b"),
      valueDataProfileArtifactId: digest("c"),
      valueDataProfileSha256: digest("d"),
      valueDataUnitId: "UA",
      modelSpecArtifactId: digest("e"),
      modelSpecProfileSha256: digest("f"),
      policySpecArtifactId: digest("1"),
      policySpecProfileSha256: digest("2"),
      calibrationRuleArtifactId: digest("3"),
      calibrationRuleProfileSha256: digest("4"),
      expectedOutputs: [{ kind: "candidate", description: "" }],
      governanceConstraints: [
        { scope: "candidate", rule: "", severity: "warning" },
      ],
    });
    const body = buildNaturalLanguageLaunchRequest(parsed, {
      locale: "en",
      preflightEnabled: true,
      autoMaterializationEnabled: true,
      maxParallelConstraint: 1,
      maxIterationsConstraint: 1,
    });

    expect(body.joint_interaction_candidate_intent).toBe(
      "n4_unique_parent_source_members.v1",
    );
    expect(body.data_source).toEqual({
      data_snapshot_ref: {
        artifact_id: digest("a"),
        kind: "fabric.data_snapshot",
        media_type: "application/json",
        manifest_profile_sha256: digest("b"),
      },
    });
    expect(body.value_data_profile_ref).toEqual({
      artifact_id: digest("c"),
      kind: "runtime.value_data_profile",
      media_type: "application/json",
      manifest_profile_sha256: digest("d"),
    });
    expect(body.value_data_unit_id).toBe("UA");
    expect(body.model_spec_ref?.kind).toBe("ir.model_spec");
    expect(body.policy_spec_ref?.kind).toBe("ir.policy_spec");
    expect(body.calibration_rule_ref?.kind).toBe(
      "ir.forecast_calibration_rule",
    );

    expect(
      naturalLanguageLaunchSchema.safeParse({
        ...parsed,
        policySpecProfileSha256: "",
      }).success,
    ).toBe(false);
    expect(
      naturalLanguageLaunchSchema.safeParse({
        ...parsed,
        modelSpecProfileSha256: "sha256:short",
      }).success,
    ).toBe(false);
  });
});
