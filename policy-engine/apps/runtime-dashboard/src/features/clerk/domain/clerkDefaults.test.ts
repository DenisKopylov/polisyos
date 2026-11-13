import { buildNaturalLanguageLaunchRequest } from "@/features/composer";

import { buildClerkFormDefaults } from "./clerkDefaults";

describe("clerk launch defaults", () => {
  it("preserves an omitted budget scope in the emitted request", () => {
    const values = buildClerkFormDefaults("model");
    const body = buildNaturalLanguageLaunchRequest(
      { ...values, nlRequest: "Assess the policy." },
      {
        locale: "en",
        preflightEnabled: true,
        autoMaterializationEnabled: true,
        maxParallelConstraint: 1,
        maxIterationsConstraint: 10,
      },
    );
    expect(values.runBudgetScope).toBe("");
    expect(body).not.toHaveProperty("run_budget_scope");
    expect(values.boundedCandidateExperiment).toBe(false);
    expect(body).not.toHaveProperty("candidate_acquisition_intent");
  });
});
