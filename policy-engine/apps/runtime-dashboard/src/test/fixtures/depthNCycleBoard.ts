import type { DepthNDomainRunProjection } from "@polisyos/runtime-api-client";

/** Source-shaped depth-N row for tests and stories that do not own a producer. */
export function depthNDomainRunFixture(
  overrides: Partial<DepthNDomainRunProjection> = {},
): DepthNDomainRunProjection {
  const runId = overrides.generation_cycle_run_id ?? "generation-cycle-fixture";
  return {
    acquisition_economics: null,
    acquisition_route: null,
    design_problem: {
      authority_profile: {
        mandate: "review the recorded owner projection",
        requested_authority_level: "research",
        requester_authority: "fixture.owner",
      },
      candidate_lever_space: {},
      design_problem_id: `design-problem-${runId}`,
      domain: "fixture",
      evidence_acquisition_needs: {},
      jurisdiction_time: {
        as_of: "2026-07-29T10:00:00Z",
        data_time: "2026-07-29T10:00:00Z",
        policy_time: "2026-07-29T10:00:00Z",
        region: "fixture-region",
        valid_time: "2026-07-29T10:00:00Z",
      },
      nl_provenance: {
        raw_request: `Review ${runId}`,
        source_surface: "fixture",
      },
      outcome_of_interest: {
        direction: "maximize",
        estimand: "fixture estimand",
        metric_id: "fixture.metric",
        target_variable: "fixture_target",
      },
      problem_statement: `Fixture problem for ${runId}`,
      schema_version: "policyos.runtime.design_problem.v1",
    },
    design_problem_ref: `design-problem://${runId}`,
    domain_role: "fixture_only",
    evidence_class: "fixture_only",
    evidence_witness: { availability: "artifact_missing" },
    generation_cycle_run_id: runId,
    search_terminal_kind: "acquisition_required",
    terminal_distribution: { fixture_only: 1 },
    weakest_links: [],
    ...overrides,
  };
}
