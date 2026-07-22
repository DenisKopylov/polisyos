import type {
  OperatorProjectionStateLabel,
  PolicyDesignCaseCloseoutTruth,
  PolicyDesignCaseProjection,
  PolicyDesignCaseProjectionBlocker,
} from "@polisyos/runtime-api-client";

export const DEFAULT_PROJECTION_USE_LIMITS = [
  "approval_authority",
  "readiness_authority",
  "runtime_closeout_authority",
  "scorecard_authority",
] as const;

type GeneratedCloseoutOwner = Pick<
  PolicyDesignCaseCloseoutTruth,
  "blockers" | "can_closeout" | "status" | "verdict"
>;

export type GeneratedProjectionAuthority = Pick<
  PolicyDesignCaseProjection,
  | "authority_role"
  | "evidence_class"
  | "generated_at"
  | "may_not_be_used_for"
  | "primary_state"
  | "projection_policy"
  | "provenance_kind"
  | "states"
  | "surface"
> & { closeout_truth: GeneratedCloseoutOwner };

function isNullableString(value: unknown): value is string | null | undefined {
  return value === undefined || value === null || typeof value === "string";
}

function isGeneratedProjectionBlocker(
  value: unknown,
): value is PolicyDesignCaseProjectionBlocker {
  if (!value || typeof value !== "object") {
    return false;
  }
  const blocker = value as Record<string, unknown>;
  return (
    typeof blocker.code === "string" &&
    typeof blocker.message === "string" &&
    isNullableString(blocker.evidence_ref) &&
    isNullableString(blocker.module_id) &&
    isNullableString(blocker.next_action) &&
    isNullableString(blocker.owner) &&
    (blocker.severity === undefined || typeof blocker.severity === "string")
  );
}

export function isGeneratedProjectionAuthority(
  value: unknown,
): value is GeneratedProjectionAuthority {
  if (!value || typeof value !== "object") {
    return false;
  }
  const projection = value as Record<string, unknown>;
  const closeoutTruth = projection.closeout_truth;
  if (!closeoutTruth || typeof closeoutTruth !== "object") {
    return false;
  }
  const closeout = closeoutTruth as Record<string, unknown>;
  const policy = projection.projection_policy;
  return (
    projection.authority_role === "projection_only" &&
    typeof projection.evidence_class === "string" &&
    typeof projection.generated_at === "string" &&
    Array.isArray(projection.may_not_be_used_for) &&
    projection.may_not_be_used_for.every(
      (purpose) => typeof purpose === "string",
    ) &&
    typeof projection.primary_state === "string" &&
    (policy === "reads_policy_design_case_only" ||
      policy === "reads_runtime_policy_design_case_graph") &&
    projection.provenance_kind === "runtime_projection" &&
    Array.isArray(projection.states) &&
    projection.states.every((state) => typeof state === "string") &&
    typeof projection.surface === "string" &&
    typeof closeout.can_closeout === "boolean" &&
    typeof closeout.status === "string" &&
    typeof closeout.verdict === "string" &&
    Array.isArray(closeout.blockers) &&
    closeout.blockers.every(isGeneratedProjectionBlocker)
  );
}

/** Preserve generated producer state without label-driven semantic inference. */
export function normalizeApiProjectionFailClosed<
  T extends GeneratedProjectionAuthority,
>(projection: T): T {
  return projection;
}

export function normalizeOperatorProjectionLabelFailClosed<
  T extends OperatorProjectionStateLabel,
>(label: T): T {
  return label;
}
