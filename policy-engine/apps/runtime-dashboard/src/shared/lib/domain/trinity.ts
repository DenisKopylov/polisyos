import {
  asArray,
  asBoolean,
  asNumber,
  asRecord,
  asString,
  toDisplayLabel,
} from "../parsing";

export type TrinityObjective = {
  id: string;
  metricId: string;
  direction: string;
  target: string;
  weight: number | null;
};

export type TrinityConstraint = {
  id: string;
  type: "hard" | "soft";
  operator: string | null;
  value: string;
};

export type TrinityStakeholder = {
  id: string;
  entityType: string;
  role: string | null;
  impactDirection: string | null;
  priority: number | null;
};

export type TrinityIntervention = {
  id: string;
  kind: string;
  targetLabel: string;
  scheduleLabel: string;
  enabled: boolean | null;
  priority: number | null;
  params: Record<string, unknown>;
};

export type TrinityAssumption = {
  id: string;
  type: string;
  description: string;
  value: string;
  confidence: number | null;
};

export type TrinityBundleView = {
  schemaVersion: string | null;
  problem: {
    id: string;
    domain: string;
    narrative: string | null;
    objectives: TrinityObjective[];
    constraints: TrinityConstraint[];
    stakeholders: TrinityStakeholder[];
    kpiCount: number;
    successCriteriaCount: number;
  };
  policy: {
    id: string;
    interventions: TrinityIntervention[];
    mechanismBindingCount: number;
    parameterCount: number;
    globalScheduleLabel: string | null;
    notes: string[];
  };
  model: {
    id: string;
    fidelityLevel: string | null;
    timeSemanticsLabel: string | null;
    assumptions: TrinityAssumption[];
    agentTypeCount: number;
    environmentParamCount: number;
    calibrated: boolean | null;
    calibrationRef: string | null;
    dataSnapshotRef: string | null;
    registryBundleRef: string | null;
  };
};

export type TrinityDiffSummary = {
  addedInterventions: string[];
  removedInterventions: string[];
  changedInterventions: Array<{
    id: string;
    changedParams: string[];
  }>;
};

function formatUnknown(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function readStringList(value: unknown): string[] {
  return asArray(value)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
}

function formatSelector(selector: unknown): string {
  const record = asRecord(selector);
  if (!record) {
    return "selector";
  }

  const clauses = asArray(record.clauses);
  if (clauses.length > 0) {
    const op = asString(record.op) ?? "any";
    return `${op.toUpperCase()}(${clauses.length})`;
  }

  const field = asString(record.field);
  const operator = asString(record.operator);
  const value = asString(record.value) ?? formatUnknown(record.value);
  if (field && operator) {
    return `${field} ${operator} ${value}`;
  }

  return asString(record.kind) ?? "selector";
}

function formatSchedule(schedule: unknown): string | null {
  const record = asRecord(schedule);
  if (!record) {
    return null;
  }

  const pieces: string[] = [];
  const kind = asString(record.kind);
  if (kind) {
    pieces.push(kind);
  }
  const frequency = asString(record.frequency);
  if (frequency) {
    pieces.push(`freq=${frequency}`);
  }
  const start = asNumber(record.start_step);
  if (start !== null) {
    pieces.push(`start=${start}`);
  }
  const end = asNumber(record.end_step);
  if (end !== null) {
    pieces.push(`end=${end}`);
  }
  const every = asNumber(record.every_n_steps);
  if (every !== null) {
    pieces.push(`every=${every}`);
  }

  return pieces.length > 0 ? pieces.join(" ") : "schedule";
}

function formatTimeSemantics(timeSemantics: unknown): string | null {
  const record = asRecord(timeSemantics);
  if (!record) {
    return null;
  }

  const unit = asString(record.step_unit) ?? asString(record.unit);
  const horizon = asNumber(record.horizon_steps) ?? asNumber(record.horizon);
  const dt = asNumber(record.dt);

  const parts: string[] = [];
  if (unit) {
    parts.push(unit);
  }
  if (horizon !== null) {
    parts.push(`${horizon} steps`);
  }
  if (dt !== null) {
    parts.push(`dt=${dt}`);
  }

  return parts.length > 0 ? parts.join(", ") : null;
}

function parseIntervention(
  value: unknown,
  index: number,
): TrinityIntervention | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }

  return {
    id: asString(record.intervention_id) ?? `intervention_${index + 1}`,
    kind: asString(record.kind) ?? "unknown",
    targetLabel: formatSelector(record.target),
    scheduleLabel: formatSchedule(record.schedule) ?? "schedule",
    enabled: asBoolean(record.enabled),
    priority: asNumber(record.priority),
    params: asRecord(record.params) ?? {},
  };
}

export function parseTrinityBundle(payload: unknown): TrinityBundleView | null {
  const root = asRecord(payload);
  if (!root) {
    return null;
  }

  const problem = asRecord(root.problem_frame);
  const policy = asRecord(root.policy_spec);
  const model = asRecord(root.model_spec);

  if (!problem || !policy || !model) {
    return null;
  }

  const objectives: TrinityObjective[] = asArray(problem.objectives)
    .map((item, index) => {
      const objective = asRecord(item);
      if (!objective) {
        return null;
      }
      return {
        id: asString(objective.objective_id) ?? `objective_${index + 1}`,
        metricId: asString(objective.metric_id) ?? "-",
        direction: asString(objective.direction) ?? "-",
        target: formatUnknown(objective.target),
        weight: asNumber(objective.weight),
      };
    })
    .filter((item): item is TrinityObjective => item !== null);

  const hardConstraints: TrinityConstraint[] = asArray(problem.hard_constraints)
    .map((item, index) => {
      const constraint = asRecord(item);
      if (!constraint) {
        return null;
      }
      return {
        id: asString(constraint.constraint_id) ?? `hard_${index + 1}`,
        type: "hard",
        operator: asString(constraint.operator),
        value: formatUnknown(constraint.value),
      };
    })
    .filter((item): item is TrinityConstraint => item !== null);

  const softConstraints: TrinityConstraint[] = asArray(problem.soft_constraints)
    .map((item, index) => {
      const constraint = asRecord(item);
      if (!constraint) {
        return null;
      }
      return {
        id: asString(constraint.constraint_id) ?? `soft_${index + 1}`,
        type: "soft",
        operator: asString(constraint.operator),
        value: formatUnknown(constraint.value),
      };
    })
    .filter((item): item is TrinityConstraint => item !== null);

  const stakeholders: TrinityStakeholder[] = asArray(problem.stakeholders)
    .map((item, index) => {
      const stakeholder = asRecord(item);
      if (!stakeholder) {
        return null;
      }
      return {
        id: asString(stakeholder.stakeholder_id) ?? `stakeholder_${index + 1}`,
        entityType: asString(stakeholder.entity_type) ?? "unknown",
        role: asString(stakeholder.role),
        impactDirection: asString(stakeholder.impact_direction),
        priority: asNumber(stakeholder.priority),
      };
    })
    .filter((item): item is TrinityStakeholder => item !== null);

  const interventions = asArray(policy.interventions)
    .map((item, index) => parseIntervention(item, index))
    .filter((item): item is TrinityIntervention => item !== null);

  const assumptions: TrinityAssumption[] = asArray(model.assumptions)
    .map((item, index) => {
      const assumption = asRecord(item);
      if (!assumption) {
        return null;
      }
      return {
        id: asString(assumption.assumption_id) ?? `assumption_${index + 1}`,
        type: asString(assumption.assumption_type) ?? "-",
        description: asString(assumption.description) ?? "",
        value: formatUnknown(assumption.value),
        confidence: asNumber(assumption.confidence),
      };
    })
    .filter((item): item is TrinityAssumption => item !== null);

  return {
    schemaVersion: asString(root.schema_version),
    problem: {
      id: asString(problem.problem_id) ?? "-",
      domain: toDisplayLabel(asString(problem.domain) ?? "unknown"),
      narrative: asString(problem.narrative),
      objectives,
      constraints: [...hardConstraints, ...softConstraints],
      stakeholders,
      kpiCount: asArray(problem.kpis).length,
      successCriteriaCount: asArray(problem.success_criteria).length,
    },
    policy: {
      id: asString(policy.policy_id) ?? "-",
      interventions,
      mechanismBindingCount: asArray(policy.mechanism_bindings).length,
      parameterCount: asArray(policy.parameters).length,
      globalScheduleLabel: formatSchedule(policy.global_schedule),
      notes: readStringList(policy.notes),
    },
    model: {
      id: asString(model.model_id) ?? "-",
      fidelityLevel: asString(model.fidelity_level),
      timeSemanticsLabel: formatTimeSemantics(model.time_semantics),
      assumptions,
      agentTypeCount: asArray(asRecord(model.agent_config)?.agent_types).length,
      environmentParamCount: asArray(asRecord(model.environment_config)?.params)
        .length,
      calibrated: asBoolean(model.calibrated),
      calibrationRef: asString(model.calibration_ref),
      dataSnapshotRef: asString(model.data_snapshot_ref),
      registryBundleRef: asString(model.registry_bundle_ref),
    },
  };
}

function jsonEquals(left: unknown, right: unknown): boolean {
  try {
    return JSON.stringify(left) === JSON.stringify(right);
  } catch {
    return String(left) === String(right);
  }
}

export function diffTrinityBundles(
  currentPayload: unknown,
  previousPayload: unknown,
): TrinityDiffSummary | null {
  const current = parseTrinityBundle(currentPayload);
  const previous = parseTrinityBundle(previousPayload);
  if (!current || !previous) {
    return null;
  }

  const currentMap = new Map(
    current.policy.interventions.map((item) => [item.id, item]),
  );
  const previousMap = new Map(
    previous.policy.interventions.map((item) => [item.id, item]),
  );

  const addedInterventions = Array.from(currentMap.keys()).filter(
    (id) => !previousMap.has(id),
  );
  const removedInterventions = Array.from(previousMap.keys()).filter(
    (id) => !currentMap.has(id),
  );

  const changedInterventions: Array<{ id: string; changedParams: string[] }> =
    [];

  for (const [id, currentIntervention] of currentMap.entries()) {
    const previousIntervention = previousMap.get(id);
    if (!previousIntervention) {
      continue;
    }

    const keys = new Set<string>([
      ...Object.keys(currentIntervention.params),
      ...Object.keys(previousIntervention.params),
    ]);

    const changedParams: string[] = [];
    for (const key of keys) {
      if (
        !jsonEquals(
          currentIntervention.params[key],
          previousIntervention.params[key],
        )
      ) {
        changedParams.push(key);
      }
    }

    if (changedParams.length > 0) {
      changedInterventions.push({
        id,
        changedParams: changedParams.sort(),
      });
    }
  }

  if (
    addedInterventions.length === 0 &&
    removedInterventions.length === 0 &&
    changedInterventions.length === 0
  ) {
    return {
      addedInterventions: [],
      removedInterventions: [],
      changedInterventions: [],
    };
  }

  return {
    addedInterventions: addedInterventions.sort(),
    removedInterventions: removedInterventions.sort(),
    changedInterventions,
  };
}
