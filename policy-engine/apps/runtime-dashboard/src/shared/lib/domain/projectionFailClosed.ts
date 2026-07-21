import type {
  OperatorProjectionStateLabel,
  PolicyDesignCaseCloseoutTruth,
  PolicyDesignCaseProjection,
} from "@polisyos/runtime-api-client";

export type ProjectionMaskingCase =
  | "conflicting"
  | "missing"
  | "non_authoritative"
  | "projection_only"
  | "reissued"
  | "stale"
  | "withdrawn";

export const DEFAULT_PROJECTION_USE_LIMITS = [
  "approval_authority",
  "readiness_authority",
  "runtime_closeout_authority",
  "scorecard_authority",
] as const;

const MASKING_CASES = [
  "missing",
  "stale",
  "conflicting",
  "reissued",
  "withdrawn",
  "non_authoritative",
  "projection_only",
] as const satisfies readonly ProjectionMaskingCase[];

const PROMOTION_LABELS = new Set([
  "approval",
  "approved",
  "pass",
  "passed",
  "publishable",
  "ready",
  "readiness_closed",
  "scorecard_pass",
]);

function stringValue(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizedToken(value: string) {
  return value
    .toLowerCase()
    .replace(/[-\s]+/gu, "_")
    .replace(/_+/gu, "_")
    .trim();
}

function normalizedText(value: string) {
  return normalizedToken(value).replace(/_/gu, " ");
}

function uniqueCases(values: ProjectionMaskingCase[]) {
  return MASKING_CASES.filter((caseId) => values.includes(caseId));
}

function collectProjectionText(value: unknown): string[] {
  if (typeof value === "string") {
    return [value];
  }
  if (Array.isArray(value)) {
    return value.flatMap(collectProjectionText);
  }
  if (!value || typeof value !== "object") {
    return [];
  }
  const record = value as Record<string, unknown>;
  const texts = [
    record.authority,
    record.authority_role,
    record.evidence_class,
    record.freshness_status,
    record.label,
    record.primary_state,
    record.projection_policy,
    record.provenance_kind,
    record.source_authority,
    record.state,
    record.status,
  ].flatMap(collectProjectionText);
  texts.push(...collectProjectionText(record.labels));
  texts.push(...collectProjectionText(record.states));
  return texts;
}

export function isProjectionPromotionLabel(value: string) {
  return PROMOTION_LABELS.has(normalizedToken(value));
}

export function detectProjectionMaskingCases(
  ...values: unknown[]
): ProjectionMaskingCase[] {
  const haystack = values
    .flatMap(collectProjectionText)
    .flatMap((value) => [normalizedToken(value), normalizedText(value)])
    .join("\n");
  const cases: ProjectionMaskingCase[] = [];

  if (/\bmissing\b/u.test(haystack)) {
    cases.push("missing");
  }
  if (/\bstale\b|\bexpired\b|\boutdated\b/u.test(haystack)) {
    cases.push("stale");
  }
  if (/\bconflict(?:ing)?\b|\bcontested\b|\bdisputed\b/u.test(haystack)) {
    cases.push("conflicting");
  }
  if (/\breissued?\b|\breissue\b|\bsuperseded\b/u.test(haystack)) {
    cases.push("reissued");
  }
  if (/\bwithdrawn\b|\bwithdrawal\b|\brevoked\b/u.test(haystack)) {
    cases.push("withdrawn");
  }
  if (
    /\bnon_authoritative\b|\bnot_authoritative\b|\bunauthoritative\b|\bnon authoritative\b|\bnot authoritative\b/u.test(
      haystack,
    )
  ) {
    cases.push("non_authoritative");
  }
  if (
    /\bprojection_only_(?:evidence|label|input|bundle|source)\b|\bprojection only (?:evidence|label|input|bundle|source)\b/u.test(
      haystack,
    )
  ) {
    cases.push("projection_only");
  }

  return uniqueCases(cases);
}

export function projectionFailClosedCodes(cases: ProjectionMaskingCase[]) {
  return cases.map((caseId) => `projection_masked_${caseId}`);
}

type GeneratedCloseoutOwner = Pick<
  PolicyDesignCaseCloseoutTruth,
  "can_closeout" | "status" | "verdict"
>;

export type GeneratedProjectionAuthority = Pick<
  PolicyDesignCaseProjection,
  | "authority_role"
  | "evidence_class"
  | "generated_at"
  | "primary_state"
  | "projection_policy"
  | "provenance_kind"
  | "states"
  | "surface"
> & { closeout_truth: GeneratedCloseoutOwner };

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
    typeof projection.primary_state === "string" &&
    (policy === "reads_policy_design_case_only" ||
      policy === "reads_runtime_policy_design_case_graph") &&
    projection.provenance_kind === "runtime_projection" &&
    Array.isArray(projection.states) &&
    projection.states.every((state) => typeof state === "string") &&
    typeof projection.surface === "string" &&
    typeof closeout.can_closeout === "boolean" &&
    typeof closeout.status === "string" &&
    typeof closeout.verdict === "string"
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
