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

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
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

function stringArray(value: unknown) {
  return Array.isArray(value)
    ? value.flatMap((item) => {
        const text = stringValue(item);
        return text ? [text] : [];
      })
    : [];
}

export function normalizeApiProjectionFailClosed(
  projection: Record<string, unknown>,
) {
  const maskingCases = detectProjectionMaskingCases(projection);
  if (maskingCases.length === 0) {
    return projection;
  }
  const states = uniqueStrings([
    ...stringArray(projection.states).filter(
      (state) => state !== "publishable",
    ),
    "projection_only",
    "blocked",
  ]);
  const labels = Array.isArray(projection.labels)
    ? projection.labels.filter((label) => {
        if (!label || typeof label !== "object") {
          return false;
        }
        const record = label as Record<string, unknown>;
        return !isProjectionPromotionLabel(
          stringValue(record.label) || stringValue(record.state),
        );
      })
    : [];

  return {
    ...projection,
    authority_role: "projection_only",
    fail_closed_codes: projectionFailClosedCodes(maskingCases),
    labels: uniqueStrings([...labels.map((label) => JSON.stringify(label))])
      .map((label) => JSON.parse(label) as Record<string, unknown>)
      .concat([
        {
          authority_role: "projection_only",
          label: "blocked projection",
          source_authority: "policy_design_case",
          state: "blocked",
        },
      ]),
    masking_cases: maskingCases,
    may_not_be_used_for: uniqueStrings([
      ...DEFAULT_PROJECTION_USE_LIMITS,
      ...stringArray(projection.may_not_be_used_for),
    ]),
    primary_state: "blocked",
    projection_policy: "reads_policy_design_case_only",
    states,
  };
}

export function normalizeOperatorProjectionLabelFailClosed<
  T extends {
    authority: "runtime_authority" | "projection_only";
    label: string;
    state: string;
  },
>(label: T): T {
  const maskingCases = detectProjectionMaskingCases(label);
  const promotionOnlyAuthority =
    label.authority === "projection_only" &&
    (isProjectionPromotionLabel(label.label) ||
      isProjectionPromotionLabel(label.state));
  if (maskingCases.length === 0 && !promotionOnlyAuthority) {
    return label;
  }
  return {
    ...label,
    authority: "projection_only",
    label: "blocked projection",
    state: "blocked",
  };
}
