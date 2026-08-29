import type { ConditionalDeltaAmount } from "@polisyos/runtime-api-client";

import {
  admitConfidenceLedgerRiskSpendPacket,
  confidenceLedgerPromotionBlockers,
  orderedConfidenceLedgerActualRows,
  type ConfidenceLedgerRiskSpendPacket,
} from "@/features/runs/domain/confidenceLedgerRiskSpend";

export const CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA = [
  "promotion_authority",
  "publication_authority",
  "public_audience",
  "bounded_completeness",
  "world_completeness",
  "family_level_total",
  "sequence_level_total",
  "cross_scope_total",
  "narrowed_claim_satisfaction",
] as const;

export type ConfidenceLedgerProtectedQuery =
  (typeof CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA)[number];
export type ConfidenceLedgerProtectedAnswer = "denied" | "not_established";
export type ConfidenceLedgerTwinBlockedReason =
  | "timeout"
  | "missing_input_or_incomplete_history"
  | "parser_or_schema_failure"
  | "unsupported_or_out_of_model"
  | "empty_consistency_set"
  | "model_observation_inconsistent"
  | "unproved_approximation";

type ObservationRecord = Readonly<{ root: HTMLElement }>;

export type ConfidenceLedgerRiskSpendEvaluationContext = Readonly<{
  consistencySet: readonly ObservationRecord[];
  controlledObservations: readonly HTMLElement[];
  declaredFiniteSchema: readonly string[];
  evaluationMode: "exact_finite_schema" | "sampled_search";
  history: readonly (HTMLElement | Uint8Array)[];
  recordModels: readonly ObservationRecord[];
  stepBudget: number;
}>;

export type ConfidenceLedgerRiskSpendTwinResult =
  | Readonly<{
      byteTwin: Uint8Array;
      protectedQueries: Readonly<
        Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
      >;
      status: "exact";
    }>
  | Readonly<{
      reason: ConfidenceLedgerTwinBlockedReason;
      status: "blocked";
    }>;

type EvaluateConfidenceLedgerRiskSpendTwinInput = Readonly<{
  context: ConfidenceLedgerRiskSpendEvaluationContext;
  packetCandidate: unknown;
  rawPacketBytes: Uint8Array;
  root: HTMLElement | null;
}>;

type VisibleFigure = Readonly<{
  canonicalDecimal: string;
  rationalDisplay: string;
  riders: string;
}>;

type VisibleSemanticLeaf = Readonly<{
  field: string;
  value: string;
}>;

type VisibleSemanticList = Readonly<{
  field: string;
  itemCount: number;
}>;

type VisibleSemanticProjection = Readonly<{
  actualRefs: readonly string[];
  actualRoles: readonly string[];
  classes: readonly string[];
  definitions: readonly string[];
  figures: readonly VisibleFigure[];
  packetMayNotUseFor: readonly string[];
  positiveAppointmentState: readonly string[];
  positivePopulationCount: readonly string[];
  positivePopulationState: readonly string[];
  promotionBlockers: readonly string[];
  replayAddress: readonly string[];
  replayPins: Readonly<Record<string, readonly string[]>>;
  routes: readonly string[];
  semanticLeaves: readonly VisibleSemanticLeaf[];
  semanticLists: readonly VisibleSemanticList[];
  sections: readonly string[];
  sourceArtifactHash: readonly string[];
  sourcePath: readonly string[];
  sourceProvenance: readonly string[];
  sourceValidationStatus: readonly string[];
  sourceValidatorId: readonly string[];
  sourceValidatorVersion: readonly string[];
  workerReceiptHash: readonly string[];
  workerReceiptRef: readonly string[];
  envelopeMayNotUseFor: readonly string[];
}>;

class SemanticDomError extends Error {}

function blocked(
  reason: ConfidenceLedgerTwinBlockedReason,
): ConfidenceLedgerRiskSpendTwinResult {
  return Object.freeze({ reason, status: "blocked" });
}

/** Create the exact evaluator record from the actual byte and DOM objects. */
export function createConfidenceLedgerRiskSpendEvaluationContext({
  rawPacketBytes,
  root,
}: Readonly<{
  rawPacketBytes: Uint8Array;
  root: HTMLElement;
}>): ConfidenceLedgerRiskSpendEvaluationContext {
  const record = Object.freeze({ root });
  return Object.freeze({
    consistencySet: Object.freeze([record]),
    controlledObservations: Object.freeze([root]),
    declaredFiniteSchema: Object.freeze([
      ...CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
    ]),
    evaluationMode: "exact_finite_schema" as const,
    history: Object.freeze([rawPacketBytes, root]),
    recordModels: Object.freeze([record]),
    stepBudget: Number.MAX_SAFE_INTEGER,
  });
}

function isElementHidden(element: HTMLElement, root: HTMLElement): boolean {
  let current: HTMLElement | null = element;
  while (current !== null) {
    const style = globalThis.getComputedStyle(current);
    const contentVisibility = (
      style as CSSStyleDeclaration & { contentVisibility?: string }
    ).contentVisibility;
    if (
      current.hidden ||
      current.getAttribute("aria-hidden") === "true" ||
      style.display === "none" ||
      style.visibility === "hidden" ||
      style.visibility === "collapse" ||
      style.opacity === "0" ||
      contentVisibility === "hidden"
    ) {
      return true;
    }
    if (current === root) break;
    current = current.parentElement;
  }
  return false;
}

function visibleText(element: HTMLElement, root: HTMLElement): string {
  if (isElementHidden(element, root)) {
    throw new SemanticDomError("semantic element is hidden");
  }
  const value = element.textContent?.trim() ?? "";
  if (value.length === 0) {
    throw new SemanticDomError("semantic element has no visible text");
  }
  return value;
}

function directListItems(list: HTMLElement): readonly HTMLElement[] {
  return [...list.children].filter(
    (child): child is HTMLElement =>
      child instanceof HTMLElement && child.tagName === "LI",
  );
}

function leafValues(
  leaves: readonly HTMLElement[],
  root: HTMLElement,
  field: string,
): readonly string[] {
  return leaves
    .filter((leaf) => leaf.dataset.confidenceLeaf === field)
    .map((leaf) => visibleText(leaf, root));
}

function indexedLeafValues(
  leaves: readonly HTMLElement[],
  root: HTMLElement,
  field: string,
): readonly string[] {
  const prefix = `${field}.`;
  return leaves
    .filter((leaf) => {
      const candidate = leaf.dataset.confidenceLeaf;
      return (
        candidate?.startsWith(prefix) === true && candidate !== `${field}.count`
      );
    })
    .map((leaf) => visibleText(leaf, root));
}

function decodeOrderedRowField(
  root: HTMLElement,
  listName: string,
  field: string,
): readonly string[] {
  const lists = [
    ...root.querySelectorAll<HTMLElement>("[data-confidence-list]"),
  ].filter((list) => list.dataset.confidenceList === listName);
  if (lists.length !== 1) return [];
  return directListItems(lists[0]).map((item) => {
    const matches = [
      ...item.querySelectorAll<HTMLElement>("[data-confidence-leaf]"),
    ].filter((leaf) => leaf.dataset.confidenceLeaf === field);
    if (matches.length !== 1) return "";
    return visibleText(matches[0], root);
  });
}

function decodeVisibleProjection(root: HTMLElement): VisibleSemanticProjection {
  const forbiddenPayloadSelector =
    'script[type="application/json"], input[type="hidden"], [data-confidence-payload], [data-testid]';
  if (
    root.matches(forbiddenPayloadSelector) ||
    root.querySelector(forbiddenPayloadSelector) !== null
  ) {
    throw new SemanticDomError(
      "raw, hidden, or test-only payload marker detected",
    );
  }
  const semanticElements = [
    ...root.querySelectorAll<HTMLElement>(
      "[data-confidence-leaf], [data-confidence-list], [data-confidence-section]",
    ),
  ];
  semanticElements.forEach((element) => {
    if (isElementHidden(element, root)) {
      throw new SemanticDomError("hidden semantic element detected");
    }
  });
  const leaves = semanticElements.filter(
    (element) => element.dataset.confidenceLeaf !== undefined,
  );
  const sections = semanticElements
    .filter((element) => element.dataset.confidenceSection !== undefined)
    .map((element) => element.dataset.confidenceSection ?? "");
  const semanticLeaves = leaves.map((leaf) =>
    Object.freeze({
      field: leaf.dataset.confidenceLeaf ?? "",
      value: visibleText(leaf, root),
    }),
  );
  const semanticLists = semanticElements
    .filter((element) => element.dataset.confidenceList !== undefined)
    .map((list) =>
      Object.freeze({
        field: list.dataset.confidenceList ?? "",
        itemCount: directListItems(list).length,
      }),
    );
  const figures = [...root.querySelectorAll<HTMLElement>("figure")].map(
    (figure): VisibleFigure => {
      if (isElementHidden(figure, root)) {
        throw new SemanticDomError("hidden amount figure detected");
      }
      const readSingle = (field: string): string => {
        const matches = [
          ...figure.querySelectorAll<HTMLElement>("[data-confidence-leaf]"),
        ].filter((leaf) => leaf.dataset.confidenceLeaf === field);
        if (matches.length !== 1) {
          throw new SemanticDomError(`amount figure ${field} is not singular`);
        }
        return visibleText(matches[0], root);
      };
      return Object.freeze({
        canonicalDecimal: readSingle("canonical-decimal"),
        rationalDisplay: readSingle("rational-display"),
        riders: readSingle("conditionality-riders"),
      });
    },
  );
  const replayPinFields = [
    "artifact_content_hash",
    "projection_hash",
    "projection_rule_version",
    "source_as_of",
    "source_dependency_hash",
  ] as const;
  return Object.freeze({
    actualRefs: decodeOrderedRowField(
      root,
      "actual-rows",
      "actual.instance_ref",
    ),
    actualRoles: decodeOrderedRowField(
      root,
      "actual-rows",
      "actual.certificate_role",
    ),
    classes: decodeOrderedRowField(
      root,
      "class-spend",
      "class.obligation_class",
    ),
    definitions: decodeOrderedRowField(
      root,
      "instrument-definitions",
      "definition.instrument_id",
    ),
    envelopeMayNotUseFor: indexedLeafValues(
      leaves,
      root,
      "posture.envelope_may_not_use_for",
    ),
    figures,
    packetMayNotUseFor: indexedLeafValues(
      leaves,
      root,
      "posture.packet_may_not_use_for",
    ),
    positiveAppointmentState: leafValues(
      leaves,
      root,
      "positive.appointment_sufficiency_state",
    ),
    positivePopulationCount: leafValues(
      leaves,
      root,
      "positive.population_count",
    ),
    positivePopulationState: leafValues(
      leaves,
      root,
      "positive.population_state",
    ),
    promotionBlockers: indexedLeafValues(
      leaves,
      root,
      "positive.promotion_blockers",
    ),
    replayAddress: leafValues(leaves, root, "replay.address"),
    replayPins: Object.freeze(
      Object.fromEntries(
        replayPinFields.map((field) => [
          field,
          leafValues(leaves, root, `replay.${field}`),
        ]),
      ),
    ),
    routes: decodeOrderedRowField(
      root,
      "certificate-routes",
      "route.certificate_class",
    ),
    semanticLeaves,
    semanticLists,
    sections,
    sourceArtifactHash: leafValues(
      leaves,
      root,
      "source.artifact_content_hash",
    ),
    sourcePath: leafValues(leaves, root, "source.relative_path"),
    sourceProvenance: indexedLeafValues(leaves, root, "source.provenance"),
    sourceValidationStatus: leafValues(
      leaves,
      root,
      "source.validation_status",
    ),
    sourceValidatorId: leafValues(leaves, root, "source.validator_id"),
    sourceValidatorVersion: leafValues(
      leaves,
      root,
      "source.validator_version",
    ),
    workerReceiptHash: leafValues(leaves, root, "source.worker_receipt_hash"),
    workerReceiptRef: leafValues(leaves, root, "source.worker_receipt_ref"),
  });
}

function figureProjection(amount: ConditionalDeltaAmount): VisibleFigure {
  return Object.freeze({
    canonicalDecimal: amount.canonical_decimal,
    rationalDisplay: amount.rational_display,
    riders: `${amount.declared_set_rider} — ${amount.locality_rider}`,
  });
}

function expectedFigures(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
): readonly VisibleFigure[] {
  const body = packet.payload;
  return [
    ...orderedConfidenceLedgerActualRows(packet).map((row) => row.spend),
    body.scope_total_risk_spend.allocation,
    body.scope_total_risk_spend.spent,
    body.scope_total_risk_spend.remaining,
    body.scope_total_risk_spend.overspend_amount,
    ...body.obligation_class_risk_spend.flatMap((row) => [
      row.allocation,
      row.spent,
      row.remaining,
      row.overspend_amount,
    ]),
  ].map(figureProjection);
}

function semanticLeaf(
  field: string,
  value: boolean | number | string | null,
): VisibleSemanticLeaf {
  return Object.freeze({
    field,
    value: value === null ? "null" : String(value),
  });
}

function appendSemanticList(
  leaves: VisibleSemanticLeaf[],
  lists: VisibleSemanticList[],
  field: string,
  values: readonly string[],
): void {
  if (values.length === 0) {
    leaves.push(semanticLeaf(`${field}.count`, 0));
    return;
  }
  lists.push(Object.freeze({ field, itemCount: values.length }));
  values.forEach((value, index) => {
    leaves.push(semanticLeaf(`${field}.${index}`, value));
  });
}

function appendAmountLeaves(
  leaves: VisibleSemanticLeaf[],
  amount: ConditionalDeltaAmount,
): void {
  leaves.push(
    semanticLeaf("rational-display", amount.rational_display),
    semanticLeaf("canonical-decimal", amount.canonical_decimal),
    semanticLeaf(
      "conditionality-riders",
      `${amount.declared_set_rider} — ${amount.locality_rider}`,
    ),
  );
}

function expectedSemanticDom(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
): Readonly<{
  leaves: readonly VisibleSemanticLeaf[];
  lists: readonly VisibleSemanticList[];
}> {
  const body = packet.payload;
  const leaves: VisibleSemanticLeaf[] = [];
  const lists: VisibleSemanticList[] = [];
  const actualRows = orderedConfidenceLedgerActualRows(packet);

  lists.push(
    Object.freeze({ field: "actual-rows", itemCount: actualRows.length }),
  );
  actualRows.forEach((row) => {
    leaves.push(
      semanticLeaf("actual.instance_ref", row.instance_ref),
      semanticLeaf("actual.certificate_role", row.certificate_role),
      semanticLeaf("actual.instrument_id", row.instrument_id),
      semanticLeaf("actual.instrument_family", row.instrument_family),
      semanticLeaf("actual.obligation_class", row.obligation_class),
      semanticLeaf("actual.execution_status", row.execution_status),
      semanticLeaf("actual.outcome", row.outcome),
      semanticLeaf("actual.certificate_ref", row.certificate_ref),
      semanticLeaf("actual.certificate_class", row.certificate_class),
      semanticLeaf("actual.certificate_route_ref", row.certificate_route_ref),
      semanticLeaf("actual.anytime_valid", row.anytime_valid),
      semanticLeaf("actual.eligible_for_promotion", row.eligible_for_promotion),
      semanticLeaf("actual.supports_obligation", row.supports_obligation),
      semanticLeaf("actual.blocker", row.blocker),
      semanticLeaf("actual.proof_profile_id", row.proof_profile_id),
      semanticLeaf(
        "actual.raw_runtime_refusal_source",
        row.raw_runtime_refusal_source,
      ),
    );
    appendAmountLeaves(leaves, row.spend);
  });

  leaves.push(semanticLeaf("scope.scope_id", body.scope_id));
  [
    body.scope_total_risk_spend.allocation,
    body.scope_total_risk_spend.spent,
    body.scope_total_risk_spend.remaining,
    body.scope_total_risk_spend.overspend_amount,
  ].forEach((amount) => appendAmountLeaves(leaves, amount));

  lists.push(
    Object.freeze({
      field: "class-spend",
      itemCount: body.obligation_class_risk_spend.length,
    }),
  );
  body.obligation_class_risk_spend.forEach((row) => {
    leaves.push(semanticLeaf("class.obligation_class", row.obligation_class));
    appendSemanticList(leaves, lists, "class.check_refs", row.check_refs);
    appendSemanticList(
      leaves,
      lists,
      "class.good_event_refs",
      row.good_event_refs,
    );
    appendSemanticList(
      leaves,
      lists,
      "class.instrument_refs",
      row.instrument_refs,
    );
    [row.allocation, row.spent, row.remaining, row.overspend_amount].forEach(
      (amount) => appendAmountLeaves(leaves, amount),
    );
  });

  lists.push(
    Object.freeze({
      field: "instrument-definitions",
      itemCount: body.instrument_definitions.length,
    }),
  );
  body.instrument_definitions.forEach((row) => {
    leaves.push(
      semanticLeaf("definition.instrument_id", row.instrument_id),
      semanticLeaf("definition.instrument_family", row.instrument_family),
      semanticLeaf("definition.proof_profile_id", row.proof_profile_id),
      semanticLeaf("definition.proof_kernel_id", row.proof_kernel_id),
      semanticLeaf("definition.guarantee_kind", row.guarantee_kind),
    );
    appendSemanticList(
      leaves,
      lists,
      "definition.certificate_roles",
      row.certificate_roles,
    );
    leaves.push(
      semanticLeaf("definition.anytime_valid", row.anytime_valid),
      semanticLeaf("definition.deterministic", row.deterministic),
      semanticLeaf(
        "definition.permits_obligation_satisfaction",
        row.permits_obligation_satisfaction,
      ),
      semanticLeaf("definition.blocker", row.blocker),
    );
  });

  lists.push(
    Object.freeze({
      field: "certificate-routes",
      itemCount: body.certificate_routes.length,
    }),
  );
  body.certificate_routes.forEach((row) => {
    Object.entries(row).forEach(([field, value]) => {
      leaves.push(
        semanticLeaf(
          `route.${field}`,
          value as boolean | number | string | null,
        ),
      );
    });
  });

  const positive = body.positive_register;
  leaves.push(
    semanticLeaf("positive.population_state", positive.population_state),
    semanticLeaf("positive.population_count", positive.population_count),
    semanticLeaf("positive.authority_posture", positive.authority_posture),
    semanticLeaf(
      "positive.appointment_denominator_state",
      positive.appointment_denominator_state,
    ),
    semanticLeaf(
      "positive.appointment_sufficiency_state",
      positive.appointment_sufficiency_state,
    ),
  );
  appendSemanticList(
    leaves,
    lists,
    "positive.promotion_blockers",
    confidenceLedgerPromotionBlockers(packet),
  );
  appendSemanticList(
    leaves,
    lists,
    "positive.register_blockers",
    positive.blockers.map((row) => `${row.slot}:${row.value}`),
  );
  appendSemanticList(
    leaves,
    lists,
    "positive.would_populate_when",
    positive.would_populate_when,
  );
  appendSemanticList(
    leaves,
    lists,
    "positive.verified_appointment_refs",
    positive.verified_appointment_refs as string[],
  );

  leaves.push(
    semanticLeaf("posture.coverage_assessment", body.coverage_assessment),
    semanticLeaf("posture.budget_posture", body.budget_posture),
    semanticLeaf("posture.appointment_posture", body.appointment_posture),
  );
  appendSemanticList(
    leaves,
    lists,
    "posture.packet_may_not_use_for",
    packet.may_not_use_for ?? [],
  );
  appendSemanticList(
    leaves,
    lists,
    "posture.envelope_may_not_use_for",
    body.coverage_envelope.may_not_use_for,
  );
  leaves.push(
    semanticLeaf(
      "good_event.clause",
      body.good_event_posture.good_event_clause,
    ),
    semanticLeaf(
      "good_event.composition_rule",
      body.good_event_posture.composition_rule,
    ),
    semanticLeaf(
      "good_event.independence_claim",
      body.good_event_posture.independence_claim,
    ),
  );
  appendSemanticList(
    leaves,
    lists,
    "good_event.executed_refs",
    body.good_event_posture.executed_probabilistic_good_event_refs,
  );
  leaves.push(
    semanticLeaf("source.relative_path", packet.source.relative_path),
    semanticLeaf(
      "source.artifact_content_hash",
      packet.source.artifact_content_hash,
    ),
    semanticLeaf("source.validator_id", packet.source.validation.validator_id),
    semanticLeaf(
      "source.validator_version",
      packet.source.validation.validator_version,
    ),
    semanticLeaf("source.validation_status", packet.source.validation.status),
    semanticLeaf(
      "source.worker_receipt_ref",
      packet.worker_validation_receipt_ref,
    ),
    semanticLeaf(
      "source.worker_receipt_hash",
      packet.worker_validation_receipt_hash,
    ),
    semanticLeaf("replay.address", packet.replay_address),
  );
  Object.entries(packet.replay_pins).forEach(([field, value]) => {
    leaves.push(semanticLeaf(`replay.${field}`, value));
  });
  appendSemanticList(
    leaves,
    lists,
    "source.provenance",
    body.source_provenance.map(
      (source) =>
        `${source.source_role}|${source.source_ref}|${source.content_hash}|${source.admission_state}|${source.availability_state}|${source.verifier_ref}`,
    ),
  );

  return Object.freeze({
    leaves: Object.freeze(leaves),
    lists: Object.freeze(lists),
  });
}

function sameSequence(
  observed: readonly unknown[],
  expected: readonly unknown[],
): boolean {
  return JSON.stringify(observed) === JSON.stringify(expected);
}

function visibleSemanticsMatch(
  observed: VisibleSemanticProjection,
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
): boolean {
  const body = packet.payload;
  const actualRows = orderedConfidenceLedgerActualRows(packet);
  const replayPinFields = Object.keys(packet.replay_pins);
  const expectedDom = expectedSemanticDom(packet);
  return (
    sameSequence(observed.sections, [
      "actual-rows",
      "risk-accounting",
      "instrument-denominators",
      "positive-register",
      "good-event-source-replay",
      "machine-export",
    ]) &&
    sameSequence(observed.semanticLeaves, expectedDom.leaves) &&
    sameSequence(observed.semanticLists, expectedDom.lists) &&
    sameSequence(
      observed.actualRefs,
      actualRows.map((row) => row.instance_ref),
    ) &&
    sameSequence(
      observed.actualRoles,
      actualRows.map((row) => row.certificate_role),
    ) &&
    sameSequence(
      observed.classes,
      body.obligation_class_risk_spend.map((row) => row.obligation_class),
    ) &&
    sameSequence(
      observed.definitions,
      body.instrument_definitions.map((row) => row.instrument_id),
    ) &&
    sameSequence(
      observed.routes,
      body.certificate_routes.map((row) => row.certificate_class),
    ) &&
    sameSequence(observed.figures, expectedFigures(packet)) &&
    sameSequence(observed.positivePopulationState, [
      body.positive_register.population_state,
    ]) &&
    sameSequence(observed.positivePopulationCount, [
      String(body.positive_register.population_count),
    ]) &&
    sameSequence(observed.positiveAppointmentState, [
      body.positive_register.appointment_sufficiency_state,
    ]) &&
    sameSequence(
      observed.promotionBlockers,
      confidenceLedgerPromotionBlockers(packet),
    ) &&
    sameSequence(observed.packetMayNotUseFor, packet.may_not_use_for ?? []) &&
    sameSequence(
      observed.envelopeMayNotUseFor,
      body.coverage_envelope.may_not_use_for,
    ) &&
    sameSequence(observed.sourcePath, [packet.source.relative_path]) &&
    sameSequence(observed.sourceArtifactHash, [
      packet.source.artifact_content_hash,
    ]) &&
    sameSequence(observed.sourceValidatorId, [
      packet.source.validation.validator_id,
    ]) &&
    sameSequence(observed.sourceValidatorVersion, [
      packet.source.validation.validator_version,
    ]) &&
    sameSequence(observed.sourceValidationStatus, [
      packet.source.validation.status,
    ]) &&
    sameSequence(observed.workerReceiptRef, [
      packet.worker_validation_receipt_ref,
    ]) &&
    sameSequence(observed.workerReceiptHash, [
      packet.worker_validation_receipt_hash,
    ]) &&
    sameSequence(observed.replayAddress, [packet.replay_address]) &&
    replayPinFields.every((field) =>
      sameSequence(observed.replayPins[field] ?? [], [
        String(packet.replay_pins[field as keyof typeof packet.replay_pins]),
      ]),
    ) &&
    sameSequence(
      observed.sourceProvenance,
      body.source_provenance.map(
        (source) =>
          `${source.source_role}|${source.source_ref}|${source.content_hash}|${source.admission_state}|${source.availability_state}|${source.verifier_ref}`,
      ),
    )
  );
}

function answersFromPacket(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
): Readonly<
  Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
> {
  const packetDenials = new Set(packet.may_not_use_for ?? []);
  const envelopeDenials = new Set(
    packet.payload.coverage_envelope.may_not_use_for,
  );
  const hasLocalityRider =
    packet.payload.fixed_scope_disclosure ===
    packet.payload.coverage_envelope.locality_rider;
  return Object.freeze({
    promotion_authority:
      packetDenials.has("promotion_authority") ||
      confidenceLedgerPromotionBlockers(packet).length > 0
        ? "denied"
        : "not_established",
    publication_authority: packetDenials.has("publication_authority")
      ? "denied"
      : "not_established",
    public_audience: packetDenials.has("public_audience")
      ? "denied"
      : "not_established",
    bounded_completeness:
      packetDenials.has("bounded_completeness") ||
      envelopeDenials.has("bounded_completeness")
        ? "denied"
        : "not_established",
    world_completeness: envelopeDenials.has("world_completeness")
      ? "denied"
      : "not_established",
    family_level_total: hasLocalityRider ? "denied" : "not_established",
    sequence_level_total: hasLocalityRider ? "denied" : "not_established",
    cross_scope_total: hasLocalityRider ? "denied" : "not_established",
    narrowed_claim_satisfaction: hasLocalityRider
      ? "denied"
      : "not_established",
  });
}

function answersFromVisibleDom(
  projection: VisibleSemanticProjection,
): Readonly<
  Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
> {
  const packetDenials = new Set(projection.packetMayNotUseFor);
  const envelopeDenials = new Set(projection.envelopeMayNotUseFor);
  const allFiguresCarryLocality =
    projection.figures.length > 0 &&
    projection.figures.every(
      (figure) =>
        figure.riders.includes("≤ δ relative to the declared obligation set") &&
        figure.riders.includes(
          "Local accounting for this exact confidence scope; no family or sequence-level claim is asserted.",
        ),
    );
  return Object.freeze({
    promotion_authority:
      packetDenials.has("promotion_authority") &&
      projection.promotionBlockers.length > 0
        ? "denied"
        : "not_established",
    publication_authority: packetDenials.has("publication_authority")
      ? "denied"
      : "not_established",
    public_audience: packetDenials.has("public_audience")
      ? "denied"
      : "not_established",
    bounded_completeness:
      packetDenials.has("bounded_completeness") ||
      envelopeDenials.has("bounded_completeness")
        ? "denied"
        : "not_established",
    world_completeness: envelopeDenials.has("world_completeness")
      ? "denied"
      : "not_established",
    family_level_total: allFiguresCarryLocality ? "denied" : "not_established",
    sequence_level_total: allFiguresCarryLocality
      ? "denied"
      : "not_established",
    cross_scope_total: allFiguresCarryLocality ? "denied" : "not_established",
    narrowed_claim_satisfaction: allFiguresCarryLocality
      ? "denied"
      : "not_established",
  });
}

function isEqualOrMoreConservative(
  observed: Readonly<
    Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
  >,
  expected: Readonly<
    Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
  >,
): boolean {
  const rank: Record<ConfidenceLedgerProtectedAnswer, number> = {
    denied: 2,
    not_established: 1,
  };
  return CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.every(
    (query) => rank[observed[query]] >= rank[expected[query]],
  );
}

function candidatePacketSchemaVersion(candidate: unknown): string | null {
  if (typeof candidate !== "object" || candidate === null) return null;
  const value = (candidate as Record<string, unknown>).packet_schema_version;
  return typeof value === "string" ? value : null;
}

/** Evaluate the byte/semantic twins with exact PV-K04 and finite-schema PV-K06. */
export async function evaluateConfidenceLedgerRiskSpendTwin({
  context,
  packetCandidate,
  rawPacketBytes,
  root,
}: EvaluateConfidenceLedgerRiskSpendTwinInput): Promise<ConfidenceLedgerRiskSpendTwinResult> {
  if (context.stepBudget <= 0) return blocked("timeout");
  if (
    root === null ||
    rawPacketBytes.byteLength === 0 ||
    !context.history.includes(root) ||
    !context.history.includes(rawPacketBytes)
  ) {
    return blocked("missing_input_or_incomplete_history");
  }
  if (context.evaluationMode !== "exact_finite_schema") {
    return blocked("unproved_approximation");
  }
  const schemaVersion = candidatePacketSchemaVersion(packetCandidate);
  if (
    schemaVersion !== null &&
    schemaVersion !== "policyos.runtime.confidence_ledger_risk_spend_packet.v1"
  ) {
    return blocked("unsupported_or_out_of_model");
  }
  if (
    !sameSequence(
      context.declaredFiniteSchema,
      CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
    )
  ) {
    return blocked("unsupported_or_out_of_model");
  }
  if (
    context.recordModels.length === 0 ||
    !context.recordModels.some((record) => record.root === root) ||
    !context.controlledObservations.includes(root)
  ) {
    return blocked("model_observation_inconsistent");
  }
  if (
    context.consistencySet.length === 0 ||
    !context.consistencySet.some((record) => record.root === root)
  ) {
    return blocked("empty_consistency_set");
  }

  let packet: ConfidenceLedgerRiskSpendPacket;
  let bytePacket: ConfidenceLedgerRiskSpendPacket;
  try {
    packet = await admitConfidenceLedgerRiskSpendPacket(packetCandidate);
    const rawCandidate: unknown = JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(rawPacketBytes),
    );
    bytePacket = await admitConfidenceLedgerRiskSpendPacket(rawCandidate);
  } catch {
    return blocked("parser_or_schema_failure");
  }
  if (!sameSequence([bytePacket], [packet])) {
    return blocked("model_observation_inconsistent");
  }
  if (packet.availability !== "available") {
    return blocked("unsupported_or_out_of_model");
  }
  const workRequired =
    root.querySelectorAll(
      "[data-confidence-leaf], [data-confidence-list], [data-confidence-section]",
    ).length + CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.length;
  if (context.stepBudget < workRequired) return blocked("timeout");

  let visible: VisibleSemanticProjection;
  try {
    visible = decodeVisibleProjection(root);
  } catch (error) {
    if (error instanceof SemanticDomError) {
      return blocked("parser_or_schema_failure");
    }
    return blocked("parser_or_schema_failure");
  }
  if (!visibleSemanticsMatch(visible, packet)) {
    return blocked("model_observation_inconsistent");
  }
  const packetAnswers = answersFromPacket(packet);
  const domAnswers = answersFromVisibleDom(visible);
  if (!isEqualOrMoreConservative(domAnswers, packetAnswers)) {
    return blocked("model_observation_inconsistent");
  }
  if (
    !sameSequence(
      Object.keys(packetAnswers),
      CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
    )
  ) {
    return blocked("unsupported_or_out_of_model");
  }
  return Object.freeze({
    byteTwin: rawPacketBytes,
    protectedQueries: packetAnswers,
    status: "exact",
  });
}
