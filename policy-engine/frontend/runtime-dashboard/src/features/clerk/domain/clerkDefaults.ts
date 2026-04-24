import type { NaturalLanguageLaunchFormValues } from "@/features/composer";

export const CLERK_DEFAULT_DOMAIN_HINTS = [
  "labor",
  "trade",
  "energy",
  "public_finance",
  "healthcare",
  "education",
  "infrastructure",
] as const;

export function buildClerkFormDefaults(
  defaultModelId: string | null,
): NaturalLanguageLaunchFormValues {
  return {
    nlRequest: "",
    executionIntent: "",
    domainHint: "",
    selectedLlmModels: defaultModelId ? [defaultModelId] : [],
    maxParallelModels: 1,
    runBudgetUsd: "",
    perModelBudgetUsd: "",
    maxIterations: 3,
    checkpointPolicy: "strict",
    nlDataSourceRef: "",
    expectedOutputs: [
      { kind: "decision_packet", description: "Policy decision summary" },
      { kind: "governance_summary", description: "Governance review" },
    ],
    governanceConstraints: [
      {
        scope: "legal",
        rule: "Comply with applicable legislation",
        severity: "error",
      },
      {
        scope: "budget",
        rule: "Stay within fiscal constraints",
        severity: "warning",
      },
    ],
  };
}
