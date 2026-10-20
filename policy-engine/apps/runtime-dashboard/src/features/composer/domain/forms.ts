import { z } from "zod";

import type { NaturalLanguageRunRequest } from "@/api/hooks/useLaunchNlRun";
import type { WorkflowRunRequest } from "@/api/hooks/useLaunchRun";

const checkpointPolicySchema = z.enum(["strict", "lenient", "disabled"]);
const manifestProfileSha256Pattern = /^sha256:[0-9a-f]{64}$/u;

const paramSchema = z.object({
  key: z.string(),
  value: z.string(),
});

const outputSchema = z.object({
  kind: z.string(),
  description: z.string(),
});

const governanceConstraintSchema = z.object({
  scope: z.string(),
  rule: z.string(),
  severity: z.string(),
});

const workflowLaunchFieldsSchema = z.object({
  dataSourceType: z.enum(["snapshot", "bindings", "view"]),
  dataSourceRef: z.string().trim().min(1),
  dataSourceProfileSha256: z
    .string()
    .trim()
    .refine(
      (value) => value === "" || manifestProfileSha256Pattern.test(value),
      "pages.composer.dataSource.profileSelectorInvalid",
    )
    .default(""),
  trinityRef: z.string(),
  policySpecRef: z.string(),
  modelSpecRef: z.string(),
  executionIntent: z.string(),
  checkpointPolicy: checkpointPolicySchema,
  expectedOutputs: z.array(outputSchema).min(1),
  governanceConstraints: z.array(governanceConstraintSchema).min(1),
  customParams: z.array(paramSchema),
});

function validateWorkflowProfileSelection(
  values: {
    dataSourceType: "snapshot" | "bindings" | "view";
    dataSourceProfileSha256: string;
  },
  context: z.RefinementCtx,
) {
  if (values.dataSourceProfileSha256 && values.dataSourceType !== "view") {
    context.addIssue({
      code: "custom",
      message: "pages.composer.dataSource.profileSelectorRequiresView",
      path: ["dataSourceProfileSha256"],
    });
  }
}

export const workflowLaunchSchema = workflowLaunchFieldsSchema.superRefine(
  validateWorkflowProfileSelection,
);

export const workflowLaunchDraftSchema = workflowLaunchFieldsSchema
  .extend({ dataSourceRef: z.string() })
  .strict()
  .superRefine(validateWorkflowProfileSelection);

export const naturalLanguageLaunchSchema = z
  .object({
    nlRequest: z.string().trim().min(1),
    executionIntent: z.string(),
    domainHint: z.string(),
    selectedLlmModels: z.array(z.string().trim().min(1)).min(1),
    maxParallelModels: z.number().int().min(1),
    runBudgetUsd: z.string(),
    perModelBudgetUsd: z.string(),
    maxIterations: z.number().int().min(1),
    checkpointPolicy: checkpointPolicySchema,
    nlDataSourceRef: z.string(),
    nlDataSourceProfileSha256: z.string().trim().default(""),
    valueDataProfileArtifactId: z.string().trim().default(""),
    valueDataProfileSha256: z.string().trim().default(""),
    valueDataUnitId: z.string().trim().default(""),
    modelSpecArtifactId: z.string().trim().default(""),
    modelSpecProfileSha256: z.string().trim().default(""),
    policySpecArtifactId: z.string().trim().default(""),
    policySpecProfileSha256: z.string().trim().default(""),
    calibrationRuleArtifactId: z.string().trim().default(""),
    calibrationRuleProfileSha256: z.string().trim().default(""),
    expectedOutputs: z.array(outputSchema).min(1),
    governanceConstraints: z.array(governanceConstraintSchema).min(1),
  })
  .superRefine((values, context) => {
    const predictiveFields = [
      "nlDataSourceProfileSha256",
      "valueDataProfileArtifactId",
      "valueDataProfileSha256",
      "valueDataUnitId",
      "modelSpecArtifactId",
      "modelSpecProfileSha256",
      "policySpecArtifactId",
      "policySpecProfileSha256",
      "calibrationRuleArtifactId",
      "calibrationRuleProfileSha256",
    ] as const;
    const selected = predictiveFields.some((field) => values[field] !== "");
    if (!selected) return;

    const requiredFields = ["nlDataSourceRef", ...predictiveFields] as const;
    for (const field of requiredFields) {
      if (values[field].trim() === "") {
        context.addIssue({
          code: "custom",
          message: "pages.composer.predictiveInputs.bundleIncomplete",
          path: [field],
        });
      }
    }
    for (const field of [
      "nlDataSourceProfileSha256",
      "valueDataProfileSha256",
      "modelSpecProfileSha256",
      "policySpecProfileSha256",
      "calibrationRuleProfileSha256",
    ] as const) {
      const value = values[field].trim();
      if (value !== "" && !manifestProfileSha256Pattern.test(value)) {
        context.addIssue({
          code: "custom",
          message: "pages.composer.predictiveInputs.profileInvalid",
          path: [field],
        });
      }
    }
  });

export type WorkflowLaunchFormInputValues = z.input<
  typeof workflowLaunchSchema
>;
export type WorkflowLaunchFormValues = z.output<typeof workflowLaunchSchema>;
export type NaturalLanguageLaunchFormInputValues = z.input<
  typeof naturalLanguageLaunchSchema
>;
export type NaturalLanguageLaunchFormValues = z.output<
  typeof naturalLanguageLaunchSchema
>;
export type ExpectedOutputFormValue = z.infer<typeof outputSchema>;
export type GovernanceConstraintFormValue = z.infer<
  typeof governanceConstraintSchema
>;
export type ParamFormValue = z.infer<typeof paramSchema>;

function toExpectedOutputSpecs(outputs: ExpectedOutputFormValue[]) {
  return outputs
    .filter((item) => item.kind.trim() || item.description.trim())
    .map((item, index) => ({
      output_id: `output_${index + 1}`,
      metric_id: item.kind.trim() || `artifact_${index + 1}`,
      comparator: ">=",
      target_value: "",
      tolerance: null,
      notes: item.description.trim() ? [item.description.trim()] : [],
    }));
}

function toGovernanceConstraintSpecs(
  constraints: GovernanceConstraintFormValue[],
) {
  return constraints
    .filter((item) => item.scope.trim() || item.rule.trim())
    .map((item, index) => ({
      constraint_id: `${item.scope.trim() || "constraint"}_${index + 1}`,
      kind: item.scope.trim() || "policy",
      severity: item.severity.trim() || "warning",
      value: item.rule.trim() ? { rule: item.rule.trim() } : {},
      notes: item.rule.trim() ? [item.rule.trim()] : [],
    }));
}

export function buildWorkflowLaunchRequest(
  values: WorkflowLaunchFormValues,
  context: {
    locale: string;
    preflightEnabled: boolean;
    autoMaterializationEnabled: boolean;
  },
): WorkflowRunRequest {
  const validatedValues = workflowLaunchSchema.parse(values);
  const selectedProfile = validatedValues.dataSourceProfileSha256.trim();
  const sourceKey =
    validatedValues.dataSourceType === "snapshot"
      ? "data_snapshot_ref"
      : validatedValues.dataSourceType === "bindings"
        ? "input_bindings_ref"
        : "data_view_request_ref";

  const params: Record<string, unknown> = {
    operator_intent: validatedValues.executionIntent.trim() || null,
    expected_outputs: toExpectedOutputSpecs(validatedValues.expectedOutputs),
    governance_constraints: toGovernanceConstraintSpecs(
      validatedValues.governanceConstraints,
    ),
    atlas_context: {
      locale_preference: context.locale,
      preflight_expected: context.preflightEnabled,
      auto_materialization: context.autoMaterializationEnabled,
    },
  };

  for (const param of validatedValues.customParams) {
    if (param.key.trim()) {
      params[param.key.trim()] = param.value;
    }
  }

  const dataSource: WorkflowRunRequest["data_source"] =
    validatedValues.dataSourceType === "view" && selectedProfile
      ? {
          data_view_request_ref: {
            artifact_id: validatedValues.dataSourceRef.trim(),
            kind: "ir.data_view_request",
            media_type: "application/json",
            manifest_profile_sha256: selectedProfile,
          },
        }
      : ({
          [sourceKey]: validatedValues.dataSourceRef.trim(),
        } as WorkflowRunRequest["data_source"]);

  const body: WorkflowRunRequest = {
    mode: "workflow",
    checkpoint_policy: validatedValues.checkpointPolicy,
    data_source: dataSource,
    params,
  };

  if (validatedValues.trinityRef.trim()) {
    body.trinity_bundle_ref = validatedValues.trinityRef.trim();
  }
  if (validatedValues.policySpecRef.trim()) {
    body.policy_spec_ref = validatedValues.policySpecRef.trim();
  }
  if (validatedValues.modelSpecRef.trim()) {
    body.model_spec_ref = validatedValues.modelSpecRef.trim();
  }

  return body;
}

export function buildNaturalLanguageLaunchRequest(
  values: NaturalLanguageLaunchFormValues,
  context: {
    locale: string;
    preflightEnabled: boolean;
    autoMaterializationEnabled: boolean;
    maxParallelConstraint: number;
    maxIterationsConstraint: number;
  },
): NaturalLanguageRunRequest {
  const models = Array.from(
    new Set(
      values.selectedLlmModels
        .map((model) => model.trim())
        .filter((model) => model.length > 0),
    ),
  );

  const parsedRunBudget = values.runBudgetUsd.trim()
    ? Number(values.runBudgetUsd)
    : null;
  const parsedPerModelBudget = values.perModelBudgetUsd.trim()
    ? Number(values.perModelBudgetUsd)
    : null;

  const body: NaturalLanguageRunRequest = {
    request: values.nlRequest.trim(),
    domain_hint: values.domainHint || null,
    max_iterations: Math.max(
      1,
      Math.min(values.maxIterations, context.maxIterationsConstraint),
    ),
    llm_model: models[0] ?? null,
    llm_models: models.length > 0 ? models : null,
    max_parallel_models: Math.max(
      1,
      Math.min(
        values.maxParallelModels,
        context.maxParallelConstraint,
        Math.max(models.length, 1),
      ),
    ),
    run_budget_usd:
      parsedRunBudget != null && Number.isFinite(parsedRunBudget)
        ? parsedRunBudget
        : null,
    per_model_budget_usd:
      parsedPerModelBudget != null && Number.isFinite(parsedPerModelBudget)
        ? parsedPerModelBudget
        : null,
    checkpoint_policy: values.checkpointPolicy,
    expected_outputs: toExpectedOutputSpecs(values.expectedOutputs),
    governance_constraints: toGovernanceConstraintSpecs(
      values.governanceConstraints,
    ),
    execution_plan: {
      operator_intent: values.executionIntent.trim() || null,
      require_preflight: context.preflightEnabled,
      auto_materialization: context.autoMaterializationEnabled,
    },
    context: {
      locale_preference: context.locale,
      dynamic_text_policy: "source_text_only",
    },
  };

  if (values.nlDataSourceRef.trim()) {
    body.data_source = {
      data_snapshot_ref: values.nlDataSourceRef.trim(),
    };
  }

  if (values.valueDataProfileArtifactId.trim()) {
    body.joint_interaction_candidate_intent =
      "n4_unique_parent_source_members.v1";
    body.data_source = {
      data_snapshot_ref: {
        artifact_id: values.nlDataSourceRef.trim(),
        kind: "fabric.data_snapshot",
        media_type: "application/json",
        manifest_profile_sha256: values.nlDataSourceProfileSha256.trim(),
      },
    };
    body.value_data_profile_ref = {
      artifact_id: values.valueDataProfileArtifactId.trim(),
      kind: "runtime.value_data_profile",
      media_type: "application/json",
      manifest_profile_sha256: values.valueDataProfileSha256.trim(),
    };
    body.value_data_unit_id = values.valueDataUnitId.trim();
    body.model_spec_ref = {
      artifact_id: values.modelSpecArtifactId.trim(),
      kind: "ir.model_spec",
      media_type: "application/json",
      manifest_profile_sha256: values.modelSpecProfileSha256.trim(),
    };
    body.policy_spec_ref = {
      artifact_id: values.policySpecArtifactId.trim(),
      kind: "ir.policy_spec",
      media_type: "application/json",
      manifest_profile_sha256: values.policySpecProfileSha256.trim(),
    };
    body.calibration_rule_ref = {
      artifact_id: values.calibrationRuleArtifactId.trim(),
      kind: "ir.forecast_calibration_rule",
      media_type: "application/json",
      manifest_profile_sha256: values.calibrationRuleProfileSha256.trim(),
    };
  }

  return body;
}
