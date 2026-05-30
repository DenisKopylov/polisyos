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

function objectArray(value: unknown) {
  return Array.isArray(value)
    ? value.flatMap((item) =>
        item && typeof item === "object"
          ? [item as Record<string, unknown>]
          : [],
      )
    : [];
}

function participationRows(projection: Record<string, unknown>) {
  return [
    ...objectArray(projection.participation_requirements),
    ...objectArray(projection.participation_requirement_evaluations),
    ...objectArray(projection.participation_evaluations),
  ];
}

function participationProjectionFailClosedCodes(
  projection: Record<string, unknown>,
) {
  const codes: string[] = [];
  for (const row of participationRows(projection)) {
    const sourceKind = normalizedToken(stringValue(row.source_kind));
    const requested = normalizedToken(stringValue(row.claim_use_requested));
    const allowed = normalizedToken(stringValue(row.claim_use_allowed));
    const representativeness = normalizedToken(
      stringValue(row.representativeness_class),
    );
    const projectionEffect = normalizedToken(
      stringValue(row.public_projection_effect),
    );

    if (
      ["llm_speculation", "analyst_summary"].includes(sourceKind) &&
      allowed !== "context_only"
    ) {
      codes.push("participation_projection_authority_leak");
    }
    if (
      requested === "prevalence" &&
      allowed === "prevalence" &&
      ["nonrepresentative", "unknown", "unverifiable"].includes(
        representativeness,
      )
    ) {
      codes.push("participation_projection_authority_leak");
    }
    if (
      projectionEffect === "supports_claim" &&
      (stringValue(row.blocker_code) || stringValue(row.downgrade_reason))
    ) {
      codes.push("participation_projection_authority_leak");
    }
    if (
      stringValue(row.raw_material_ref) ||
      stringValue(row.raw_transcript_ref) ||
      row.raw_transcript
    ) {
      codes.push("participation_projection_privacy_leak");
    }
  }
  return uniqueStrings(codes);
}

function closeoutTruthMissing(projection: Record<string, unknown>) {
  const closeoutTruth = projection.closeout_truth;
  if (!closeoutTruth || typeof closeoutTruth !== "object") {
    return true;
  }
  const record = closeoutTruth as Record<string, unknown>;
  return typeof record.can_closeout !== "boolean";
}

export function normalizeApiProjectionFailClosed(
  projection: Record<string, unknown>,
) {
  const maskingCases = detectProjectionMaskingCases(projection);
  const participationCodes = participationProjectionFailClosedCodes(projection);
  const missingCloseoutTruth = closeoutTruthMissing(projection);
  if (
    maskingCases.length === 0 &&
    participationCodes.length === 0 &&
    !missingCloseoutTruth
  ) {
    return projection;
  }
  const failClosedCodes = uniqueStrings([
    ...projectionFailClosedCodes(maskingCases),
    ...participationCodes,
    ...(missingCloseoutTruth ? ["projection_closeout_truth_missing"] : []),
    ...stringArray(projection.fail_closed_codes),
  ]);
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
    closeout_truth: missingCloseoutTruth
      ? {
          blocker_codes: ["projection_closeout_truth_missing"],
          blockers: [
            {
              code: "projection_closeout_truth_missing",
              message:
                "Dashboard projection is missing boolean closeout truth.",
              severity: "fail",
            },
          ],
          can_closeout: false,
          contested_state: "not_contested",
          limitation_codes: [],
          omission_codes: [],
          status: "blocked",
          verdict: "cannot_closeout",
        }
      : projection.closeout_truth,
    fail_closed_codes: failClosedCodes,
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
      ...(participationCodes.length ? ["participation_authority"] : []),
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
