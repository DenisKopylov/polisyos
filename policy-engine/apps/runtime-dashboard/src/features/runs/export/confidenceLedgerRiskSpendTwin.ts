import type { ConditionalDeltaAmount } from "@polisyos/runtime-api-client";

import {
  CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
  CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
  confidenceLedgerPromotionBlockers,
  evaluateConfidenceLedgerProtectedQuery,
  orderedConfidenceLedgerActualRows,
  type ConfidenceLedgerProtectedAnswer,
  type ConfidenceLedgerProtectedQuery,
  type ConfidenceLedgerRiskSpendPacket,
  type ConfidenceLedgerSafetyBlockedReason,
} from "@/features/runs/domain/confidenceLedgerRiskSpend";
import en from "@/shared/i18n/locales/en.json";
import uk from "@/shared/i18n/locales/uk.json";

export type ConfidenceLedgerTwinBlockedReason =
  ConfidenceLedgerSafetyBlockedReason;

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
  evaluationMode: "exact_finite_schema" | "sampled_search";
  packetCandidate: unknown;
  rawPacketBytes: Uint8Array;
  root: HTMLElement | null;
  stepBudget: number;
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

function isElementHidden(element: HTMLElement, root: HTMLElement): boolean {
  let current: HTMLElement | null = element;
  while (current !== null) {
    const style = globalThis.getComputedStyle(current);
    const contentVisibility = (
      style as CSSStyleDeclaration & { contentVisibility?: string }
    ).contentVisibility;
    const clip =
      `${style.getPropertyValue("clip")} ${current.style.getPropertyValue("clip")}`.replaceAll(
        ",",
        " ",
      );
    const clipPath = `${style.clipPath} ${current.style.clipPath}`;
    const overflow = `${style.overflow} ${current.style.overflow}`;
    const positioned =
      style.position === "absolute" ||
      style.position === "fixed" ||
      current.style.position === "absolute" ||
      current.style.position === "fixed";
    const width = Number.parseFloat(style.width || current.style.width);
    const height = Number.parseFloat(style.height || current.style.height);
    const left = Number.parseFloat(style.left || current.style.left);
    const top = Number.parseFloat(style.top || current.style.top);
    const rect = current.getBoundingClientRect();
    if (
      current.hidden ||
      current.getAttribute("aria-hidden") === "true" ||
      current.classList.contains("sr-only") ||
      current.classList.contains("visually-hidden") ||
      style.display === "none" ||
      style.visibility === "hidden" ||
      style.visibility === "collapse" ||
      style.opacity === "0" ||
      contentVisibility === "hidden" ||
      /rect\(\s*0(?:px)?\s+0(?:px)?\s+0(?:px)?\s+0(?:px)?\s*\)/u.test(clip) ||
      /inset\(\s*(?:50|100)%/u.test(clipPath) ||
      (positioned &&
        Number.isFinite(width) &&
        Number.isFinite(height) &&
        width <= 1 &&
        height <= 1 &&
        /hidden|clip/u.test(overflow)) ||
      (positioned && Number.isFinite(left) && left < -999) ||
      (positioned && Number.isFinite(top) && top < -999) ||
      (positioned &&
        (rect.right < -999 ||
          rect.bottom < -999 ||
          (rect.width <= 1 &&
            rect.height <= 1 &&
            /hidden|clip/u.test(overflow)))) ||
      Number.parseFloat(style.textIndent || current.style.textIndent) < -999
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

type GovernedText = Readonly<{ marker: string; text: string }>;
type ProductLocale = "en" | "uk";

const CONFIDENCE_LEDGER_DOM_NODE_CAP = 20 * 1000;
const CONFIDENCE_LEDGER_DOM_TEXT_CODE_UNIT_CAP = 80 * 1000;
const CONFIDENCE_LEDGER_DOM_WORK_RESERVE = 120 * 1000;

function normalizedText(value: string): string {
  return value
    .replace(/\s+/gu, " ")
    .replace(/\s+([:;,.!?])/gu, "$1")
    .trim();
}

function documentDomWithinCaps(document: Document): boolean {
  const documentElement = document.documentElement;
  if (documentElement === null) return false;
  const showAll = document.defaultView?.NodeFilter.SHOW_ALL ?? 0xffffffff;
  const walker = document.createTreeWalker(documentElement, showAll);
  let nodeCount = 1;
  let textCodeUnits = 0;
  let node = walker.nextNode();
  while (node !== null) {
    nodeCount += 1;
    if (node.nodeType === Node.TEXT_NODE) {
      textCodeUnits += node.nodeValue?.length ?? 0;
    }
    if (
      nodeCount > CONFIDENCE_LEDGER_DOM_NODE_CAP ||
      textCodeUnits > CONFIDENCE_LEDGER_DOM_TEXT_CODE_UNIT_CAP
    ) {
      return false;
    }
    node = walker.nextNode();
  }
  return true;
}

type ExpectedEnvelopeField = Readonly<{
  field: string;
  label: string;
  values: readonly string[];
}>;

function deriveExpectedEnvelopeFields(
  envelope: unknown,
): readonly ExpectedEnvelopeField[] {
  const fields: ExpectedEnvelopeField[] = [];
  const append = (field: string, value: unknown): void => {
    if (Array.isArray(value)) {
      if (value.every((item) => item === null || typeof item !== "object")) {
        fields.push({
          field,
          label: field,
          values: value.map((item) => (item === null ? "null" : String(item))),
        });
        return;
      }
      value.forEach((item, index) => append(`${field}.${index}`, item));
      return;
    }
    if (typeof value === "object" && value !== null) {
      Object.entries(value).forEach(([nestedField, nestedValue]) =>
        append(field ? `${field}.${nestedField}` : nestedField, nestedValue),
      );
      return;
    }
    fields.push({
      field,
      label: field,
      values: [value === null ? "null" : String(value)],
    });
  };
  append("", envelope);
  return Object.freeze(fields);
}

function catalogText(
  locale: ProductLocale,
  path: string,
  variables: Readonly<Record<string, string | number>> = {},
): string {
  let current: unknown = locale === "uk" ? uk : en;
  for (const segment of path.split(".")) {
    if (
      typeof current !== "object" ||
      current === null ||
      !(segment in current)
    ) {
      throw new SemanticDomError(`locale copy is missing ${path}`);
    }
    current = (current as Record<string, unknown>)[segment];
  }
  if (typeof current !== "string") {
    throw new SemanticDomError(`locale copy is not text ${path}`);
  }
  return normalizedText(
    Object.entries(variables).reduce(
      (message, [name, value]) =>
        message.replaceAll(`{${name}}`, String(value)),
      current,
    ),
  );
}

function collectGovernedText(boundary: HTMLElement): readonly GovernedText[] {
  const forbiddenPayloadSelector =
    'script[type="application/json"], input[type="hidden"], [data-confidence-payload], [data-testid]';
  if (
    boundary.matches(forbiddenPayloadSelector) ||
    boundary.querySelector(forbiddenPayloadSelector) !== null
  ) {
    throw new SemanticDomError("hidden or test-only payload detected");
  }
  const document = boundary.ownerDocument;
  const showText = document.defaultView?.NodeFilter.SHOW_TEXT ?? 4;
  const walker = document.createTreeWalker(boundary, showText);
  const byElement = new Map<HTMLElement, { marker: string; parts: string[] }>();
  let node = walker.nextNode();
  while (node !== null) {
    const text = normalizedText(node.textContent ?? "");
    if (text.length > 0) {
      const parent = node.parentElement;
      if (parent === null)
        throw new SemanticDomError("visible text has no parent");
      if (!isElementHidden(parent, boundary)) {
        const classified = parent.closest<HTMLElement>(
          "[data-confidence-text]",
        );
        if (classified === null || !boundary.contains(classified)) {
          throw new SemanticDomError(`unclassified visible text: ${text}`);
        }
        const marker = classified.dataset.confidenceText;
        if (marker === undefined || marker.length === 0) {
          throw new SemanticDomError("empty governed text marker");
        }
        const existing = byElement.get(classified);
        if (existing === undefined) {
          byElement.set(classified, { marker, parts: [text] });
        } else {
          existing.parts.push(text);
        }
      }
    }
    node = walker.nextNode();
  }
  const classifiedElements = [
    ...boundary.querySelectorAll<HTMLElement>("[data-confidence-text]"),
  ];
  if (boundary.dataset.confidenceText !== undefined) {
    classifiedElements.unshift(boundary);
  }
  for (const element of classifiedElements) {
    if (isElementHidden(element, boundary)) {
      throw new SemanticDomError("governed text is visually hidden");
    }
    if (!byElement.has(element)) {
      throw new SemanticDomError("governed text marker has no visible text");
    }
  }
  return Object.freeze(
    [...byElement.values()].map(({ marker, parts }) =>
      Object.freeze({ marker, text: normalizedText(parts.join(" ")) }),
    ),
  );
}

function expectedRootText(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
  locale: ProductLocale,
): readonly GovernedText[] {
  const result: GovernedText[] = [];
  const body = packet.payload;
  const push = (marker: string, value: boolean | number | string | null) =>
    result.push(
      Object.freeze({
        marker,
        text: normalizedText(value === null ? "null" : String(value)),
      }),
    );
  const semantic = (field: string, value: boolean | number | string | null) =>
    push(`leaf.${field}`, value);
  const detail = (
    label: string,
    field: string,
    value: boolean | number | string | null,
  ) => {
    push(`detail.label.${label}`, label);
    semantic(field, value);
  };
  const list = (label: string, field: string, values: readonly string[]) => {
    push(`detail.label.${label}`, label);
    if (values.length === 0) {
      semantic(`${field}.count`, 0);
    } else {
      values.forEach((value, index) => semantic(`${field}.${index}`, value));
    }
  };
  const figure = (label: string, amount: ConditionalDeltaAmount) => {
    push("figure.caption", label);
    push("figure.rational_display", amount.rational_display);
    push(
      "figure.canonical_decimal_label",
      `${catalogText(locale, "pages.cycleBoard.confidenceLedger.figure.canonicalDecimal")}:`,
    );
    push("figure.canonical_decimal", amount.canonical_decimal);
    push(
      "figure.conditionality_riders",
      `${amount.declared_set_rider} — ${amount.locality_rider}`,
    );
  };
  const section = (name: string, copyPath: string) =>
    push(`section.${name}.title`, catalogText(locale, copyPath));
  const accountingCopy = (name: string) =>
    catalogText(locale, `pages.cycleBoard.confidenceLedger.accounting.${name}`);

  section(
    "actual-rows",
    "pages.cycleBoard.confidenceLedger.sections.actualRows",
  );
  const actualFields = [
    "instance_ref",
    "certificate_role",
    "instrument_id",
    "instrument_family",
    "obligation_class",
    "execution_status",
    "outcome",
    "certificate_ref",
    "certificate_class",
    "certificate_route_ref",
    "anytime_valid",
    "eligible_for_promotion",
    "supports_obligation",
    "blocker",
    "proof_profile_id",
    "raw_runtime_refusal_source",
  ] as const;
  orderedConfidenceLedgerActualRows(packet).forEach((row) => {
    actualFields.forEach((field) =>
      detail(field, `actual.${field}`, row[field] as boolean | string | null),
    );
    figure(`${row.instance_ref} · ${accountingCopy("spent")}`, row.spend);
  });

  section(
    "risk-accounting",
    "pages.cycleBoard.confidenceLedger.sections.riskAccounting",
  );
  semantic("scope.scope_id", body.scope_id);
  const scopePrefix = accountingCopy("scopeTotal");
  (
    [
      ["allocation", body.scope_total_risk_spend.allocation],
      ["spent", body.scope_total_risk_spend.spent],
      ["remaining", body.scope_total_risk_spend.remaining],
      ["overspend", body.scope_total_risk_spend.overspend_amount],
    ] as const
  ).forEach(([name, amount]) =>
    figure(`${scopePrefix} · ${accountingCopy(name)}`, amount),
  );
  body.obligation_class_risk_spend.forEach((row) => {
    semantic("class.obligation_class", row.obligation_class);
    list("check_refs", "class.check_refs", row.check_refs);
    list("good_event_refs", "class.good_event_refs", row.good_event_refs);
    list("instrument_refs", "class.instrument_refs", row.instrument_refs);
    (
      [
        ["allocation", row.allocation],
        ["spent", row.spent],
        ["remaining", row.remaining],
        ["overspend", row.overspend_amount],
      ] as const
    ).forEach(([name, amount]) =>
      figure(`${row.obligation_class} · ${accountingCopy(name)}`, amount),
    );
  });

  section(
    "instrument-denominators",
    "pages.cycleBoard.confidenceLedger.sections.denominators",
  );
  push(
    "denominators.instrument_definitions.title",
    catalogText(
      locale,
      "pages.cycleBoard.confidenceLedger.instrumentDefinitions",
    ),
  );
  body.instrument_definitions.forEach((row) => {
    detail("instrument_id", "definition.instrument_id", row.instrument_id);
    detail(
      "instrument_family",
      "definition.instrument_family",
      row.instrument_family,
    );
    detail(
      "proof_profile_id",
      "definition.proof_profile_id",
      row.proof_profile_id,
    );
    detail(
      "proof_kernel_id",
      "definition.proof_kernel_id",
      row.proof_kernel_id,
    );
    detail("guarantee_kind", "definition.guarantee_kind", row.guarantee_kind);
    list(
      "certificate_roles",
      "definition.certificate_roles",
      row.certificate_roles,
    );
    detail("anytime_valid", "definition.anytime_valid", row.anytime_valid);
    detail("deterministic", "definition.deterministic", row.deterministic);
    detail(
      "permits_obligation_satisfaction",
      "definition.permits_obligation_satisfaction",
      row.permits_obligation_satisfaction,
    );
    detail("blocker", "definition.blocker", row.blocker);
  });
  push(
    "denominators.certificate_routes.title",
    catalogText(locale, "pages.cycleBoard.confidenceLedger.certificateRoutes"),
  );
  body.certificate_routes.forEach((row) => {
    Object.entries(row).forEach(([field, value]) =>
      detail(
        field,
        `route.${field}`,
        value as boolean | number | string | null,
      ),
    );
  });

  section(
    "positive-register",
    "pages.cycleBoard.confidenceLedger.sections.positiveRegister",
  );
  push(
    "positive.empty.title",
    catalogText(
      locale,
      "pages.cycleBoard.confidenceLedger.positiveEmpty.title",
    ),
  );
  push(
    "positive.empty.body",
    catalogText(
      locale,
      "pages.cycleBoard.confidenceLedger.positiveEmpty.body",
      {
        authority: body.positive_register.authority_posture.replaceAll(
          "_",
          " ",
        ),
        count: body.positive_register.population_count,
      },
    ),
  );
  detail(
    "population_state",
    "positive.population_state",
    body.positive_register.population_state,
  );
  detail(
    "population_count",
    "positive.population_count",
    body.positive_register.population_count,
  );
  detail(
    "authority_posture",
    "positive.authority_posture",
    body.positive_register.authority_posture,
  );
  detail(
    "appointment_denominator_state",
    "positive.appointment_denominator_state",
    body.positive_register.appointment_denominator_state,
  );
  detail(
    "appointment_sufficiency_state",
    "positive.appointment_sufficiency_state",
    body.positive_register.appointment_sufficiency_state,
  );
  list(
    "promotion_blockers",
    "positive.promotion_blockers",
    confidenceLedgerPromotionBlockers(packet),
  );
  list(
    "register_blockers",
    "positive.register_blockers",
    body.positive_register.blockers.map((row) => `${row.slot}:${row.value}`),
  );
  list(
    "would_populate_when",
    "positive.would_populate_when",
    body.positive_register.would_populate_when,
  );
  list(
    "verified_appointment_refs",
    "positive.verified_appointment_refs",
    body.positive_register.verified_appointment_refs as string[],
  );

  section(
    "good-event-source-replay",
    "pages.cycleBoard.confidenceLedger.sections.goodEventSourceReplay",
  );
  detail(
    "coverage_assessment",
    "posture.coverage_assessment",
    body.coverage_assessment,
  );
  detail("budget_posture", "posture.budget_posture", body.budget_posture);
  detail(
    "appointment_posture",
    "posture.appointment_posture",
    body.appointment_posture,
  );
  list(
    "packet_may_not_use_for",
    "posture.packet_may_not_use_for",
    packet.may_not_use_for,
  );
  list(
    "envelope_may_not_use_for",
    "posture.envelope_may_not_use_for",
    body.coverage_envelope.may_not_use_for,
  );
  detail(
    "good_event_clause",
    "good_event.clause",
    body.good_event_posture.good_event_clause,
  );
  detail(
    "composition_rule",
    "good_event.composition_rule",
    body.good_event_posture.composition_rule,
  );
  detail(
    "independence_claim",
    "good_event.independence_claim",
    body.good_event_posture.independence_claim,
  );
  list(
    "executed_probabilistic_good_event_refs",
    "good_event.executed_refs",
    body.good_event_posture.executed_probabilistic_good_event_refs,
  );
  detail(
    "source.relative_path",
    "source.relative_path",
    packet.source.relative_path,
  );
  detail(
    "source.artifact_content_hash",
    "source.artifact_content_hash",
    packet.source.artifact_content_hash,
  );
  detail(
    "source.validator_id",
    "source.validator_id",
    packet.source.validation.validator_id,
  );
  detail(
    "source.validator_version",
    "source.validator_version",
    packet.source.validation.validator_version,
  );
  detail(
    "source.validation.status",
    "source.validation_status",
    packet.source.validation.status,
  );
  detail(
    "worker_validation_receipt_ref",
    "source.worker_receipt_ref",
    packet.worker_validation_receipt_ref,
  );
  detail(
    "worker_validation_receipt_hash",
    "source.worker_receipt_hash",
    packet.worker_validation_receipt_hash,
  );
  detail("replay_address", "replay.address", packet.replay_address);
  Object.entries(packet.replay_pins).forEach(([field, value]) =>
    detail(`replay_pins.${field}`, `replay.${field}`, value),
  );
  list(
    "source_provenance",
    "source.provenance",
    body.source_provenance.map(
      (source) =>
        `${source.source_role}|${source.source_ref}|${source.content_hash}|${source.admission_state}|${source.availability_state}|${source.verifier_ref}`,
    ),
  );

  section(
    "machine-export",
    "pages.cycleBoard.confidenceLedger.sections.machineExport",
  );
  push(
    "machine.download",
    catalogText(locale, "pages.cycleBoard.confidenceLedger.downloadMachine"),
  );
  return Object.freeze(result);
}

function expectedDialogText(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
  locale: ProductLocale,
  figureLabel: string,
): readonly GovernedText[] {
  const result: GovernedText[] = [
    Object.freeze({
      marker: "dialog.title",
      text: `${figureLabel}: ${catalogText(
        locale,
        "pages.cycleBoard.confidenceLedger.figure.dialogTitle",
      )}`,
    }),
    Object.freeze({
      marker: "dialog.description",
      text: catalogText(
        locale,
        "pages.cycleBoard.confidenceLedger.figure.dialogDescription",
      ),
    }),
  ];
  deriveExpectedEnvelopeFields(packet.payload.coverage_envelope).forEach(
    ({ field, label, values }) => {
      result.push(
        Object.freeze({ marker: `dialog.field.${field}.label`, text: label }),
      );
      if (values.length === 0) {
        result.push(
          Object.freeze({ marker: `dialog.field.${field}.empty`, text: "[]" }),
        );
      } else {
        values.forEach((value, index) =>
          result.push(
            Object.freeze({
              marker: `dialog.field.${field}.value.${index}`,
              text: normalizedText(value),
            }),
          ),
        );
      }
    },
  );
  return Object.freeze(result);
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

/** Evaluate the byte/semantic twins with exact PV-K04 and finite-schema PV-K06. */
export async function evaluateConfidenceLedgerRiskSpendTwin({
  evaluationMode,
  packetCandidate,
  rawPacketBytes,
  root,
  stepBudget,
}: EvaluateConfidenceLedgerRiskSpendTwinInput): Promise<ConfidenceLedgerRiskSpendTwinResult> {
  if (
    !Number.isFinite(stepBudget) ||
    !Number.isSafeInteger(stepBudget) ||
    stepBudget <= 0 ||
    stepBudget > CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET ||
    stepBudget <= CONFIDENCE_LEDGER_DOM_WORK_RESERVE
  ) {
    return blocked("timeout");
  }
  if (root === null) return blocked("missing_input_or_incomplete_history");

  const preflight = await evaluateConfidenceLedgerProtectedQuery({
    evaluationMode,
    packetCandidate,
    rawPacketBytes,
    stepBudget: stepBudget - CONFIDENCE_LEDGER_DOM_WORK_RESERVE,
  });
  if (preflight.status === "blocked") return blocked(preflight.reason);
  const packet = preflight.packet;
  if (packet.availability !== "available") {
    return blocked("unsupported_or_out_of_model");
  }

  const envelopeRef = packet.payload.coverage_envelope_ref;
  if (
    !root.ownerDocument.documentElement.contains(root) ||
    !documentDomWithinCaps(root.ownerDocument)
  ) {
    return blocked("unsupported_or_out_of_model");
  }
  if (
    root.dataset.confidenceEnvelopeRef !== envelopeRef ||
    (root.dataset.confidenceLocale !== "en" &&
      root.dataset.confidenceLocale !== "uk")
  ) {
    return blocked("model_observation_inconsistent");
  }
  const locale = root.dataset.confidenceLocale;
  const dialogs = [
    ...root.ownerDocument.querySelectorAll<HTMLElement>(
      "[data-confidence-dialog-envelope-ref]",
    ),
  ].filter(
    (dialog) => dialog.dataset.confidenceDialogEnvelopeRef === envelopeRef,
  );
  if (dialogs.length === 0) {
    return blocked("missing_input_or_incomplete_history");
  }
  if (dialogs.length !== 1) return blocked("model_observation_inconsistent");
  const dialog = dialogs[0];

  let visible: VisibleSemanticProjection;
  let rootText: readonly GovernedText[];
  let dialogText: readonly GovernedText[];
  try {
    visible = decodeVisibleProjection(root);
    rootText = collectGovernedText(root);
    dialogText = collectGovernedText(dialog);
  } catch (error) {
    if (error instanceof SemanticDomError) {
      return blocked("parser_or_schema_failure");
    }
    return blocked("parser_or_schema_failure");
  }
  if (!visibleSemanticsMatch(visible, packet)) {
    return blocked("model_observation_inconsistent");
  }
  const expectedRoot = expectedRootText(packet, locale);
  const figureLabel = dialog.dataset.confidenceDialogFigureLabel;
  const allowedFigureLabels = expectedRoot
    .filter((entry) => entry.marker === "figure.caption")
    .map((entry) => entry.text);
  if (
    figureLabel === undefined ||
    !allowedFigureLabels.includes(normalizedText(figureLabel))
  ) {
    return blocked("model_observation_inconsistent");
  }
  if (
    !sameSequence(rootText, expectedRoot) ||
    !sameSequence(
      dialogText,
      expectedDialogText(packet, locale, normalizedText(figureLabel)),
    )
  ) {
    return blocked("model_observation_inconsistent");
  }
  const domAnswers = answersFromVisibleDom(visible);
  if (!isEqualOrMoreConservative(domAnswers, preflight.protectedQueries)) {
    return blocked("model_observation_inconsistent");
  }
  if (
    !sameSequence(
      Object.keys(preflight.protectedQueries),
      CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
    )
  ) {
    return blocked("unsupported_or_out_of_model");
  }
  return Object.freeze({
    byteTwin: preflight.rawPacketBytes,
    protectedQueries: preflight.protectedQueries,
    status: "exact",
  });
}
