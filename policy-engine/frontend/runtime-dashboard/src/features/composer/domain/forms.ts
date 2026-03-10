import { z } from "zod";

import type { NaturalLanguageRunRequest } from "@/api/hooks/useLaunchNlRun";
import type { WorkflowRunRequest } from "@/api/hooks/useLaunchRun";

const checkpointPolicySchema = z.enum(["strict", "lenient", "disabled"]);

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

export const workflowLaunchSchema = z.object({
  dataSourceType: z.enum(["snapshot", "bindings", "view"]),
  dataSourceRef: z.string().trim().min(1),
  trinityRef: z.string(),
  policySpecRef: z.string(),
  modelSpecRef: z.string(),
  executionIntent: z.string(),
  checkpointPolicy: checkpointPolicySchema,
  expectedOutputs: z.array(outputSchema).min(1),
  governanceConstraints: z.array(governanceConstraintSchema).min(1),
  customParams: z.array(paramSchema),
});

export const naturalLanguageLaunchSchema = z.object({
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
  expectedOutputs: z.array(outputSchema).min(1),
  governanceConstraints: z.array(governanceConstraintSchema).min(1),
});

export type WorkflowLaunchFormValues = z.infer<typeof workflowLaunchSchema>;
export type NaturalLanguageLaunchFormValues = z.infer<
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
  const sourceKey =
    values.dataSourceType === "snapshot"
      ? "data_snapshot_ref"
      : values.dataSourceType === "bindings"
        ? "input_bindings_ref"
        : "data_view_request_ref";

  const params: Record<string, unknown> = {
    operator_intent: values.executionIntent.trim() || null,
    expected_outputs: toExpectedOutputSpecs(values.expectedOutputs),
    governance_constraints: toGovernanceConstraintSpecs(
      values.governanceConstraints,
    ),
    atlas_context: {
      locale_preference: context.locale,
      preflight_expected: context.preflightEnabled,
      auto_materialization: context.autoMaterializationEnabled,
    },
  };

  for (const param of values.customParams) {
    if (param.key.trim()) {
      params[param.key.trim()] = param.value;
    }
  }

  const body: WorkflowRunRequest = {
    mode: "workflow",
    checkpoint_policy: values.checkpointPolicy,
    data_source: {
      [sourceKey]: values.dataSourceRef.trim(),
    } as WorkflowRunRequest["data_source"],
    params,
  };

  if (values.trinityRef.trim()) {
    body.trinity_bundle_ref = values.trinityRef.trim();
  }
  if (values.policySpecRef.trim()) {
    body.policy_spec_ref = values.policySpecRef.trim();
  }
  if (values.modelSpecRef.trim()) {
    body.model_spec_ref = values.modelSpecRef.trim();
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

  return body;
}
