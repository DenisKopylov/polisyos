import { diffTrinityBundles, parseTrinityBundle } from "@/lib/domain/trinity";

function createTrinityBundle() {
  return {
    model_spec: {
      agent_config: { agent_types: ["household", "firm"] },
      assumptions: [
        {
          assumption_id: "ass-1",
          assumption_type: "elasticity",
          confidence: "0.8",
          description: "Demand elasticity",
          value: 0.3,
        },
      ],
      calibrated: "false",
      calibration_ref: "cal-1",
      data_snapshot_ref: "snapshot-1",
      environment_config: { params: [1, 2, 3] },
      fidelity_level: "high",
      model_id: "model-1",
      registry_bundle_ref: "registry-1",
      time_semantics: { dt: 1, horizon_steps: 12, step_unit: "month" },
    },
    policy_spec: {
      global_schedule: { end_step: 12, frequency: "weekly", kind: "global" },
      interventions: [
        {
          enabled: "true",
          intervention_id: "int-1",
          kind: "tax_credit",
          params: { amount: 100, phase_in: [1, 2] },
          priority: "1",
          schedule: {
            every_n_steps: 3,
            frequency: "monthly",
            kind: "recurring",
            start_step: 1,
          },
          target: { field: "income", operator: ">=", value: 1000 },
        },
        {
          intervention_id: "int-2",
          kind: "grant",
          params: { enabled: true },
          target: { clauses: [{ field: "region" }], op: "all" },
        },
      ],
      mechanism_bindings: ["binding-1", "binding-2"],
      notes: ["note-1", 2],
      parameters: ["param-1"],
      policy_id: "policy-1",
    },
    problem_frame: {
      domain: "tax_policy",
      hard_constraints: [
        { constraint_id: "hard-1", operator: "<=", value: 0.2 },
      ],
      kpis: ["gdp"],
      narrative: "Target household relief",
      objectives: [
        {
          direction: "maximize",
          metric_id: "gdp_change",
          objective_id: "obj-1",
          target: 1.2,
          weight: "0.7",
        },
      ],
      problem_id: "problem-1",
      soft_constraints: [
        { constraint_id: "soft-1", operator: ">=", value: "0.5" },
      ],
      stakeholders: [
        {
          entity_type: "household",
          impact_direction: "positive",
          priority: "2",
          role: "beneficiary",
          stakeholder_id: "stakeholder-1",
        },
      ],
      success_criteria: ["net-benefit"],
    },
    schema_version: "1.0.0",
  } as Record<string, unknown>;
}

describe("trinity domain", () => {
  it("parses trinity bundles into UI-friendly summaries", () => {
    expect(parseTrinityBundle(null)).toBeNull();

    const parsed = parseTrinityBundle(createTrinityBundle());

    expect(parsed).toEqual({
      model: {
        agentTypeCount: 2,
        assumptions: [
          {
            confidence: 0.8,
            description: "Demand elasticity",
            id: "ass-1",
            type: "elasticity",
            value: "0.3",
          },
        ],
        calibrated: false,
        calibrationRef: "cal-1",
        dataSnapshotRef: "snapshot-1",
        environmentParamCount: 3,
        fidelityLevel: "high",
        id: "model-1",
        registryBundleRef: "registry-1",
        timeSemanticsLabel: "month, 12 steps, dt=1",
      },
      policy: {
        globalScheduleLabel: "global freq=weekly end=12",
        id: "policy-1",
        interventions: [
          {
            enabled: true,
            id: "int-1",
            kind: "tax_credit",
            params: { amount: 100, phase_in: [1, 2] },
            priority: 1,
            scheduleLabel: "recurring freq=monthly start=1 every=3",
            targetLabel: "income >= 1000",
          },
          {
            enabled: null,
            id: "int-2",
            kind: "grant",
            params: { enabled: true },
            priority: null,
            scheduleLabel: "schedule",
            targetLabel: "ALL(1)",
          },
        ],
        mechanismBindingCount: 2,
        notes: ["note-1", "2"],
        parameterCount: 1,
      },
      problem: {
        constraints: [
          {
            id: "hard-1",
            operator: "<=",
            type: "hard",
            value: "0.2",
          },
          {
            id: "soft-1",
            operator: ">=",
            type: "soft",
            value: "0.5",
          },
        ],
        domain: "Tax Policy",
        id: "problem-1",
        kpiCount: 1,
        narrative: "Target household relief",
        objectives: [
          {
            direction: "maximize",
            id: "obj-1",
            metricId: "gdp_change",
            target: "1.2",
            weight: 0.7,
          },
        ],
        stakeholders: [
          {
            entityType: "household",
            id: "stakeholder-1",
            impactDirection: "positive",
            priority: 2,
            role: "beneficiary",
          },
        ],
        successCriteriaCount: 1,
      },
      schemaVersion: "1.0.0",
    });
  });

  it("diffs intervention additions, removals, and param changes", () => {
    const current = createTrinityBundle();
    const previous = createTrinityBundle();

    (previous.policy_spec as { interventions: unknown[] }).interventions = [
      {
        ...(
          previous.policy_spec as { interventions: Record<string, unknown>[] }
        ).interventions[0],
        params: { amount: 80, phase_in: [1] },
      },
      {
        intervention_id: "int-3",
        kind: "subsidy",
        params: { amount: 20 },
        target: { value: "all_households" },
      },
    ];

    expect(diffTrinityBundles(current, previous)).toEqual({
      addedInterventions: ["int-2"],
      changedInterventions: [
        { changedParams: ["amount", "phase_in"], id: "int-1" },
      ],
      removedInterventions: ["int-3"],
    });

    expect(diffTrinityBundles(current, current)).toEqual({
      addedInterventions: [],
      changedInterventions: [],
      removedInterventions: [],
    });
    expect(diffTrinityBundles(current, null)).toBeNull();
  });
});
