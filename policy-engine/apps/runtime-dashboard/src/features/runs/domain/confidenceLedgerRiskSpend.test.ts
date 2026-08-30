import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";

import {
  CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
  CONFIDENCE_LEDGER_OWNER_LITERAL_RULES,
  CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
  admitConfidenceLedgerRiskSpendPacket,
  confidenceLedgerPromotionBlockers,
  evaluateConfidenceLedgerProtectedQuery,
  orderedConfidenceLedgerActualRows,
} from "./confidenceLedgerRiskSpend";

type OpenApiSchema = Readonly<{
  $ref?: string;
  additionalProperties?: OpenApiSchema | boolean;
  allOf?: readonly OpenApiSchema[];
  anyOf?: readonly OpenApiSchema[];
  const?: unknown;
  enum?: readonly unknown[];
  items?: OpenApiSchema;
  oneOf?: readonly OpenApiSchema[];
  properties?: Readonly<Record<string, OpenApiSchema>>;
}>;

type OpenApiDocument = Readonly<{
  components: Readonly<{
    schemas: Readonly<Record<string, OpenApiSchema>>;
  }>;
  paths: Record<string, unknown>;
}>;

function openApiDocument(): OpenApiDocument {
  return JSON.parse(
    readFileSync(
      resolve(process.cwd(), "../../schemas/runtime_api_v1.openapi.json"),
      "utf8",
    ),
  ) as OpenApiDocument;
}

function availablePacket(): AvailableConfidenceLedgerRiskSpendPacket {
  const openApi = openApiDocument() as OpenApiDocument & {
    paths: Record<
      string,
      {
        get: {
          responses: Record<
            string,
            {
              content: Record<
                string,
                {
                  examples: {
                    default: {
                      value: AvailableConfidenceLedgerRiskSpendPacket;
                    };
                  };
                }
              >;
            }
          >;
        };
      }
    >;
  };
  return structuredClone(
    openApi.paths[
      "/api/v1/exports/governed-projections/confidence-ledger-risk-spend"
    ].get.responses["200"].content["application/json"].examples.default.value,
  );
}

function generatedOwnerLiteralInventory() {
  const openApi = openApiDocument();
  const rootSchemas = [
    "AvailableConfidenceLedgerRiskSpendPacket",
    "SourceBlockedConfidenceLedgerRiskSpendPacket",
    "ArtifactMissingConfidenceLedgerRiskSpendPacket",
    "InvalidConfidenceLedgerRiskSpendPacket",
  ] as const;
  const rules: Array<{
    path: string;
    rootSchema: (typeof rootSchemas)[number];
    value: boolean | number | string;
  }> = [];
  const walk = (
    rootSchema: (typeof rootSchemas)[number],
    schema: OpenApiSchema,
    path: string,
    refs: ReadonlySet<string>,
  ): void => {
    if (schema.$ref !== undefined) {
      const name = schema.$ref.split("/").at(-1);
      if (name === undefined || refs.has(name)) return;
      const referenced = openApi.components.schemas[name];
      if (referenced === undefined) {
        throw new Error(`unresolved OpenAPI schema reference ${schema.$ref}`);
      }
      walk(rootSchema, referenced, path, new Set([...refs, name]));
    }
    const singleton =
      schema.const ?? (schema.enum?.length === 1 ? schema.enum[0] : undefined);
    if (
      typeof singleton === "boolean" ||
      typeof singleton === "number" ||
      typeof singleton === "string"
    ) {
      rules.push({ path, rootSchema, value: singleton });
    }
    for (const branch of ["allOf", "oneOf", "anyOf"] as const) {
      schema[branch]?.forEach((nested) =>
        walk(rootSchema, nested, path, new Set(refs)),
      );
    }
    Object.entries(schema.properties ?? {}).forEach(([field, nested]) =>
      walk(rootSchema, nested, `${path}/${field}`, new Set(refs)),
    );
    if (schema.items !== undefined) {
      walk(rootSchema, schema.items, `${path}/*`, new Set(refs));
    }
    if (
      typeof schema.additionalProperties === "object" &&
      schema.additionalProperties !== null
    ) {
      walk(rootSchema, schema.additionalProperties, `${path}/*`, new Set(refs));
    }
  };
  rootSchemas.forEach((rootSchema) => {
    const schema = openApi.components.schemas[rootSchema];
    if (schema === undefined) throw new Error(`missing root ${rootSchema}`);
    walk(rootSchema, schema, "", new Set([rootSchema]));
  });
  return rules.sort((left, right) =>
    `${left.rootSchema}${left.path}`.localeCompare(
      `${right.rootSchema}${right.path}`,
    ),
  );
}

function canonicalJson(value: unknown): string {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "number" ||
    typeof value === "string"
  ) {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .filter((key) => record[key] !== undefined)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(",")}}`;
  }
  throw new TypeError("unsupported canonical JSON test value");
}

async function fingerprint(value: unknown): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(canonicalJson(value)),
  );
  return `sha256:${[...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")}`;
}

async function refreshSelfHashes(
  packet: AvailableConfidenceLedgerRiskSpendPacket,
): Promise<void> {
  const payloadBody = structuredClone(packet.payload) as unknown as Record<
    string,
    unknown
  >;
  Reflect.deleteProperty(payloadBody, "projection_hash");
  packet.payload.projection_hash = await fingerprint(payloadBody);

  const packetBody = structuredClone(packet) as unknown as Record<
    string,
    unknown
  >;
  Reflect.deleteProperty(packetBody, "projection_hash");
  Reflect.deleteProperty(packetBody, "replay_address");
  Reflect.deleteProperty(packetBody, "replay_pins");
  const freshness = packetBody.freshness as Record<string, unknown>;
  Reflect.deleteProperty(freshness, "observed_at");
  packet.projection_hash = await fingerprint(packetBody);
  packet.replay_pins.projection_hash = packet.projection_hash;
  packet.replay_address = `${packet.stable_address}?${new URLSearchParams({
    artifact_content_hash: packet.replay_pins.artifact_content_hash,
    projection_hash: packet.replay_pins.projection_hash,
    projection_rule_version: packet.replay_pins.projection_rule_version,
    source_as_of: packet.replay_pins.source_as_of,
    source_dependency_hash: packet.replay_pins.source_dependency_hash,
  }).toString()}`;
}

async function refreshSemanticOwnerHashes(
  packet: AvailableConfidenceLedgerRiskSpendPacket,
): Promise<void> {
  const semantic = packet.payload.semantic_ledger_basis;
  const semanticBody = structuredClone(semantic) as unknown as Record<
    string,
    unknown
  >;
  Reflect.deleteProperty(semanticBody, "projection_hash");
  semantic.projection_hash = await fingerprint(semanticBody);
  packet.payload.source_projection_hash = semantic.projection_hash;
  packet.payload.coverage_envelope.source_identities[1].content_hash =
    semantic.projection_hash;
  packet.payload.source_provenance[1].content_hash = semantic.projection_hash;
  packet.frozen_semantic_projection_hash = semantic.projection_hash;
  packet.source.validation.frozen_semantic_projection_hash =
    semantic.projection_hash;
  packet.source.validation.semantic_projection_hash = semantic.projection_hash;
  await refreshEnvelopeAndAmountHashes(packet);
}

async function refreshConsumerSelfBoundRegistryHashes(
  packet: AvailableConfidenceLedgerRiskSpendPacket,
): Promise<void> {
  const body = packet.payload;
  const registryContentHash = await fingerprint(body.registry_basis);
  const registryProjectionHash = await fingerprint({
    fixture_kind: "consumer_self_bound_registry_projection",
    registry_basis: body.registry_basis,
    registry_content_hash: registryContentHash,
  });
  body.registry_content_hash = registryContentHash;
  packet.registry_content_hash = registryContentHash;
  packet.registry_projection_hash = registryProjectionHash;
  packet.source.validation.registry_content_hash = registryContentHash;
  packet.source.validation.registry_projection_hash = registryProjectionHash;
  body.coverage_envelope.source_identities[0].content_hash =
    registryContentHash;
  body.source_provenance[0].content_hash = registryContentHash;

  for (const route of body.certificate_routes) {
    route.registry_content_hash = registryContentHash;
    const routeBody = structuredClone(route) as unknown as Record<
      string,
      unknown
    >;
    Reflect.deleteProperty(routeBody, "route_binding_hash");
    route.route_binding_hash = await fingerprint(routeBody);
  }
  body.certificate_route_denominator_hash = await fingerprint(
    body.certificate_routes.map((route) => route.route_binding_hash),
  );

  const semantic = body.semantic_ledger_basis;
  semantic.registry_content_hash = registryContentHash;
  semantic.root_projection_hash = await fingerprint({
    authority_provenance: semantic.authority_provenance,
    budget_delta: semantic.budget_delta,
    budget_delta_decimal: semantic.budget_delta_decimal,
    conditionality_clause: semantic.conditionality_clause,
    deployment_identity: semantic.deployment_identity,
    maintained_assumptions: semantic.maintained_assumptions,
    projection_scope: semantic.projection_scope,
    registry_content_hash: semantic.registry_content_hash,
    risk_scope: semantic.risk_scope,
    schedule_profile_hash: semantic.schedule_profile_hash,
    schedule_profile_id: semantic.schedule_profile_id,
    schedule_projection_hash: semantic.schedule_projection_hash,
    schema_version: semantic.schema_version,
    scope_anchor_ref: semantic.scope_anchor_ref,
    scope_id: semantic.scope_id,
  });

  let head = semantic.root_projection_hash;
  const filtrationByRequest = new Map<string, string>();
  const currentChecks = new Map<
    string,
    (typeof semantic.events)[number]["check"]
  >();
  for (const event of semantic.events) {
    const check = event.check;
    check.registry_content_hash = registryContentHash;
    if (
      event.event_type === "prepared" ||
      (!filtrationByRequest.has(check.request_key) &&
        check.outcome === "preflight_refusal")
    ) {
      filtrationByRequest.set(check.request_key, head);
    }
    const filtrationProjectionHash = filtrationByRequest.get(check.request_key);
    if (filtrationProjectionHash === undefined) {
      throw new Error("consumer fixture lacks a semantic preparation event");
    }
    check.filtration_projection_hash = filtrationProjectionHash;
    check.claim_execution_projection_hash = await fingerprint({
      certificate_role: check.certificate_role,
      claim_polarity: check.claim_polarity,
      claim_ref: check.claim_ref,
      claim_scope_ref: check.claim_scope_ref,
      data_window_ref: check.data_window_ref,
      execution_id: check.execution_id,
      execution_ordinal: check.execution_ordinal,
      filtration_projection_hash: check.filtration_projection_hash,
      instrument_definition_hash: check.instrument_definition_hash,
      null_ref: check.null_ref,
      proof_profile_hash: check.proof_profile_hash,
      registry_content_hash: check.registry_content_hash,
      request_fingerprint: check.request_fingerprint,
      reserved_alpha: check.spend,
      schedule_query_index: check.schedule_query_index,
      scope_id: check.scope_id,
    });
    const checkBody = structuredClone(check) as unknown as Record<
      string,
      unknown
    >;
    Reflect.deleteProperty(checkBody, "check_projection_hash");
    check.check_projection_hash = await fingerprint(checkBody);

    event.parent_event_projection_hash = head;
    const eventBody = structuredClone(event) as unknown as Record<
      string,
      unknown
    >;
    Reflect.deleteProperty(eventBody, "event_projection_hash");
    event.event_projection_hash = await fingerprint(eventBody);
    head = event.event_projection_hash;
    currentChecks.set(check.request_key, structuredClone(check));
  }
  semantic.head_event_projection_hash = head;
  semantic.checks = [...currentChecks]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([, check]) => check);

  const declaredClassesHash = await fingerprint(
    body.coverage_envelope.declared_obligation_classes,
  );
  for (const amount of conditionalAmounts(packet)) {
    amount.declared_obligation_classes_hash = declaredClassesHash;
  }
  await refreshSemanticOwnerHashes(packet);

  const declaredContentHash = await fingerprint({
    fixture_kind: "consumer_self_bound_declared_content",
    projection_hash: body.projection_hash,
    registry_projection_hash: registryProjectionHash,
  });
  const artifactContentHash = await fingerprint({
    declared_content_hash: declaredContentHash,
    fixture_kind: "consumer_self_bound_artifact",
    source_projection_hash: body.source_projection_hash,
  });
  const dependencyHash = await fingerprint({
    artifact_content_hash: artifactContentHash,
    fixture_kind: "consumer_self_bound_dependency_receipt",
    registry_projection_hash: registryProjectionHash,
  });
  const workerReceiptHash = await fingerprint({
    artifact_content_hash: artifactContentHash,
    dependency_hash: dependencyHash,
    fixture_kind: "consumer_self_bound_worker_receipt",
    registry_content_hash: registryContentHash,
    semantic_projection_hash: semantic.projection_hash,
    status: "passed",
  });
  packet.source.declared_content_hash = declaredContentHash;
  packet.source.artifact_content_hash = artifactContentHash;
  packet.source.validation.bound_artifact_content_hash = artifactContentHash;
  packet.source.validation.bound_dependency_aggregate_identity = dependencyHash;
  packet.source.validation.worker_validation_receipt_hash = workerReceiptHash;
  packet.source_dependency_hash = dependencyHash;
  packet.worker_validation_receipt_hash = workerReceiptHash;
  packet.worker_validation_receipt_ref = `owner-validation:${workerReceiptHash}`;
  packet.replay_pins.artifact_content_hash = artifactContentHash;
  packet.replay_pins.source_dependency_hash = dependencyHash;
  await refreshSelfHashes(packet);
}

function rotateFirstTwo(values: unknown[]): void {
  if (values.length < 2) throw new Error("owner order cannot be rotated");
  [values[0], values[1]] = [values[1], values[0]];
}

async function evolveConsumerSelfBoundOwnerInventory(
  packet: AvailableConfidenceLedgerRiskSpendPacket,
): Promise<void> {
  const body = packet.payload;
  const classPool = body.registry_basis.obligation_pools.find(
    (pool) => pool.obligation_classes.length > 1,
  );
  if (classPool === undefined) {
    throw new Error("owner registry has no multi-class obligation pool");
  }
  rotateFirstTwo(classPool.obligation_classes);
  const obligationOrder = body.registry_basis.obligation_pools.flatMap(
    (pool) => pool.obligation_classes,
  );
  body.coverage_envelope.declared_obligation_classes = [...obligationOrder];
  const classRows = new Map(
    body.obligation_class_risk_spend.map((row) => [row.obligation_class, row]),
  );
  body.obligation_class_risk_spend = obligationOrder.map((obligationClass) => {
    const row = classRows.get(obligationClass);
    if (row === undefined) throw new Error("owner class row is missing");
    return row;
  });

  const usedCertificateClasses = new Set(
    body.semantic_ledger_basis.checks.flatMap((check) =>
      check.certificate_class === null ? [] : [check.certificate_class],
    ),
  );
  const retiredRoute = body.registry_basis.certificate_class_routes.find(
    (route) => !usedCertificateClasses.has(route.certificate_class),
  );
  if (retiredRoute === undefined) {
    throw new Error("owner registry has no unused certificate route");
  }
  body.registry_basis.certificate_class_routes =
    body.registry_basis.certificate_class_routes.filter(
      (route) => route.certificate_class !== retiredRoute.certificate_class,
    );
  body.certificate_routes = body.certificate_routes.filter(
    (route) => route.certificate_class !== retiredRoute.certificate_class,
  );
  rotateFirstTwo(body.registry_basis.certificate_class_routes);
  const routes = new Map(
    body.certificate_routes.map((row) => [row.certificate_class, row]),
  );
  body.certificate_routes = body.registry_basis.certificate_class_routes.map(
    (route) => {
      const row = routes.get(route.certificate_class);
      if (row === undefined) throw new Error("owner route row is missing");
      return row;
    },
  );
  body.certificate_route_denominator_count = body.certificate_routes.length;

  const usedInstrumentIds = new Set([
    ...body.semantic_ledger_basis.checks.map((check) => check.instrument_id),
    ...body.registry_basis.certificate_class_routes.map(
      (route) => route.instrument_id,
    ),
  ]);
  const retiredInstrument = body.registry_basis.instruments.find(
    (instrument) =>
      !usedInstrumentIds.has(instrument.instrument_id) &&
      !instrument.certificate_roles.includes("promotion_conformance"),
  );
  if (retiredInstrument === undefined) {
    throw new Error("owner registry has no unused non-conformance instrument");
  }
  body.registry_basis.instruments = body.registry_basis.instruments.filter(
    (instrument) =>
      instrument.instrument_id !== retiredInstrument.instrument_id,
  );
  body.instrument_definitions = body.instrument_definitions.filter(
    (instrument) =>
      instrument.instrument_id !== retiredInstrument.instrument_id,
  );
  rotateFirstTwo(body.registry_basis.instruments);
  const definitions = new Map(
    body.instrument_definitions.map((row) => [row.instrument_id, row]),
  );
  body.instrument_definitions = body.registry_basis.instruments.map(
    (instrument) => {
      const row = definitions.get(instrument.instrument_id);
      if (row === undefined) throw new Error("owner instrument row is missing");
      return row;
    },
  );
  await refreshConsumerSelfBoundRegistryHashes(packet);
}

async function refreshAmountHash(
  amount: AvailableConfidenceLedgerRiskSpendPacket["payload"]["total_spend"],
  envelopeHash: string,
): Promise<void> {
  amount.coverage_envelope_hash = envelopeHash;
  amount.coverage_envelope_ref = `coverage-envelope:${envelopeHash}`;
  const amountBody = structuredClone(amount) as unknown as Record<
    string,
    unknown
  >;
  Reflect.deleteProperty(amountBody, "amount_hash");
  amount.amount_hash = await fingerprint(amountBody);
}

function conditionalAmounts(
  packet: AvailableConfidenceLedgerRiskSpendPacket,
): Array<AvailableConfidenceLedgerRiskSpendPacket["payload"]["total_spend"]> {
  return [
    packet.payload.total_spend,
    packet.payload.scope_total_risk_spend.allocation,
    packet.payload.scope_total_risk_spend.spent,
    packet.payload.scope_total_risk_spend.remaining,
    packet.payload.scope_total_risk_spend.overspend_amount,
    ...packet.payload.obligation_class_risk_spend.flatMap((row) => [
      row.allocation,
      row.spent,
      row.remaining,
      row.overspend_amount,
    ]),
    ...packet.payload.grouped_spend.map((row) => row.spend),
    ...packet.payload.instrument_instances.map((row) => row.spend),
  ];
}

async function refreshEnvelopeAndAmountHashes(
  packet: AvailableConfidenceLedgerRiskSpendPacket,
): Promise<void> {
  const envelope = packet.payload.coverage_envelope;
  const assessmentKeyBody = {
    owner_scope_key: envelope.owner_scope_key,
    protected_action_id: envelope.protected_action_id,
    rule_version: envelope.rule_version,
    scope_id: envelope.scope_id,
    sources: envelope.source_identities,
  };
  envelope.assessment_key = await fingerprint(assessmentKeyBody);
  const envelopeBody = structuredClone(envelope) as unknown as Record<
    string,
    unknown
  >;
  Reflect.deleteProperty(envelopeBody, "envelope_hash");
  Reflect.deleteProperty(envelopeBody, "envelope_ref");
  envelope.envelope_hash = await fingerprint(envelopeBody);
  envelope.envelope_ref = `coverage-envelope:${envelope.envelope_hash}`;
  packet.payload.coverage_envelope_ref = envelope.envelope_ref;

  await Promise.all(
    conditionalAmounts(packet).map((amount) =>
      refreshAmountHash(amount, envelope.envelope_hash),
    ),
  );
  await refreshSelfHashes(packet);
}

function setAmount(
  amount: AvailableConfidenceLedgerRiskSpendPacket["payload"]["total_spend"],
  numerator: number,
  denominator: number,
  decimal: string,
): void {
  amount.amount = { denominator, numerator };
  amount.rational_display = `${numerator}/${denominator}`;
  amount.canonical_decimal = decimal;
}

function replaceEveryRationalDenominator(
  value: unknown,
  denominator: number,
): number {
  if (value === null || typeof value !== "object") return 0;
  if (Array.isArray(value)) {
    return value.reduce<number>(
      (count, item) =>
        count + replaceEveryRationalDenominator(item, denominator),
      0,
    );
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.denominator === "number" &&
    typeof record.numerator === "number"
  ) {
    record.denominator = denominator;
    return 1;
  }
  return Object.values(record).reduce<number>(
    (count, item) => count + replaceEveryRationalDenominator(item, denominator),
    0,
  );
}

async function forgeCoherentAvailableOverspend(
  packet: AvailableConfidenceLedgerRiskSpendPacket,
): Promise<void> {
  const body = packet.payload;
  const semantic = body.semantic_ledger_basis;
  const changedCheck = semantic.checks[0];
  changedCheck.spend = { denominator: 50, numerator: 1 };
  changedCheck.spend_decimal = "0.02";
  semantic.total_spend = { denominator: 50, numerator: 1 };
  semantic.total_spend_decimal = "0.02";
  semantic.within_budget = false;
  const semanticBody = structuredClone(semantic) as unknown as Record<
    string,
    unknown
  >;
  Reflect.deleteProperty(semanticBody, "projection_hash");
  semantic.projection_hash = await fingerprint(semanticBody);

  body.source_projection_hash = semantic.projection_hash;
  body.coverage_envelope.source_identities[1].content_hash =
    semantic.projection_hash;
  body.source_provenance[1].content_hash = semantic.projection_hash;
  packet.frozen_semantic_projection_hash = semantic.projection_hash;
  packet.source.validation.frozen_semantic_projection_hash =
    semantic.projection_hash;
  packet.source.validation.semantic_projection_hash = semantic.projection_hash;
  packet.source.validation.recomputed_total_spend_numerator = 1;
  packet.source.validation.recomputed_total_spend_denominator = 50;

  setAmount(body.instrument_instances[0].spend, 1, 50, "0.02");
  const grouped = body.grouped_spend.find(
    (row) =>
      row.obligation_class === changedCheck.obligation_class &&
      row.instrument_id === changedCheck.instrument_id,
  );
  if (grouped === undefined) throw new Error("grouped spend row is missing");
  setAmount(grouped.spend, 1, 50, "0.02");
  const classRow = body.obligation_class_risk_spend.find(
    (row) => row.obligation_class === changedCheck.obligation_class,
  );
  if (classRow === undefined) throw new Error("class spend row is missing");
  setAmount(classRow.spent, 1, 50, "0.02");
  setAmount(classRow.remaining, 0, 1, "0");
  setAmount(classRow.overspend_amount, 29, 1500, "0.019(3)");
  setAmount(body.total_spend, 1, 50, "0.02");
  setAmount(body.scope_total_risk_spend.spent, 1, 50, "0.02");
  setAmount(body.scope_total_risk_spend.remaining, 0, 1, "0");
  setAmount(body.scope_total_risk_spend.overspend_amount, 1, 100, "0.01");
  body.budget_posture = "over_spend";
  await refreshEnvelopeAndAmountHashes(packet);
}

function commonTransport(packet: AvailableConfidenceLedgerRiskSpendPacket) {
  return {
    as_of: packet.as_of,
    authoritative_for: packet.authoritative_for,
    export_replay_contract: packet.export_replay_contract,
    intended_audience: packet.intended_audience,
    intended_audiences: packet.intended_audiences,
    may_not_use_for: packet.may_not_use_for,
    packet_schema_version: packet.packet_schema_version,
    projection_id: packet.projection_id,
    projection_rule_version: packet.projection_rule_version,
    stable_address: packet.stable_address,
  };
}

async function refreshTransportIdentity(packet: {
  as_of: string;
  freshness: { observed_at: string };
  projection_hash: string;
  replay_address: string;
  replay_pins: {
    artifact_content_hash: string;
    projection_hash: string;
    projection_rule_version: string;
    source_as_of: string;
    source_dependency_hash: string;
  };
  stable_address: string;
  [key: string]: unknown;
}): Promise<void> {
  const packetBody = structuredClone(packet) as Record<string, unknown>;
  Reflect.deleteProperty(packetBody, "projection_hash");
  Reflect.deleteProperty(packetBody, "replay_address");
  Reflect.deleteProperty(packetBody, "replay_pins");
  const freshness = packetBody.freshness as Record<string, unknown>;
  Reflect.deleteProperty(freshness, "observed_at");
  packet.projection_hash = await fingerprint(packetBody);
  packet.replay_pins.projection_hash = packet.projection_hash;
  packet.replay_address = `${packet.stable_address}?${new URLSearchParams({
    artifact_content_hash: packet.replay_pins.artifact_content_hash,
    projection_hash: packet.replay_pins.projection_hash,
    projection_rule_version: packet.replay_pins.projection_rule_version,
    source_as_of: packet.replay_pins.source_as_of,
    source_dependency_hash: packet.replay_pins.source_dependency_hash,
  }).toString()}`;
}

describe("confidence-ledger risk-spend strict admission", () => {
  it("covers every generated owner const and single-value enum with the runtime literal table", () => {
    const generated = generatedOwnerLiteralInventory();
    const runtime = [...CONFIDENCE_LEDGER_OWNER_LITERAL_RULES].sort(
      (left, right) =>
        `${left.rootSchema}${left.path}`.localeCompare(
          `${right.rootSchema}${right.path}`,
        ),
    );

    expect(generated).toHaveLength(99);
    expect(runtime).toEqual(generated);
  });

  it("admits the specialized available packet and resolves actual rows by producer refs", async () => {
    const packet = availablePacket();

    const admitted = await admitConfidenceLedgerRiskSpendPacket(packet);
    expect(admitted.availability).toBe("available");
    if (admitted.availability !== "available") {
      throw new Error("available fixture admitted as a non-available arm");
    }
    const actualRows = orderedConfidenceLedgerActualRows({
      ...admitted,
      payload: {
        ...admitted.payload,
        instrument_instances: [
          ...admitted.payload.instrument_instances,
        ].reverse(),
      },
    });
    expect(actualRows.map((row) => row.instance_ref)).toEqual([
      ...packet.payload.refusal_instance_refs,
      ...packet.payload.acquisition_instance_refs,
    ]);
    expect(actualRows.map((row) => row.certificate_role)).toEqual([
      "refusal",
      "acquisition",
      "acquisition",
    ]);
  });

  it("admits a consumer-self-bound owner evolution without a UI-owned denominator", async () => {
    const baseline = availablePacket();
    const evolved = availablePacket();
    await evolveConsumerSelfBoundOwnerInventory(evolved);
    const rawOwnerMutation = availablePacket();
    rawOwnerMutation.payload.registry_basis = structuredClone(
      evolved.payload.registry_basis,
    );

    await expect(
      admitConfidenceLedgerRiskSpendPacket(rawOwnerMutation),
    ).rejects.toThrow(/contract_error/iu);

    const baselineClasses =
      baseline.payload.registry_basis.obligation_pools.flatMap(
        (pool) => pool.obligation_classes,
      );
    const evolvedClasses =
      evolved.payload.registry_basis.obligation_pools.flatMap(
        (pool) => pool.obligation_classes,
      );
    expect(new Set(evolvedClasses)).toEqual(new Set(baselineClasses));
    expect(evolvedClasses).not.toEqual(baselineClasses);

    const baselineInstrumentIds =
      baseline.payload.registry_basis.instruments.map(
        (instrument) => instrument.instrument_id,
      );
    const evolvedInstrumentIds = evolved.payload.registry_basis.instruments.map(
      (instrument) => instrument.instrument_id,
    );
    expect(evolvedInstrumentIds).toHaveLength(baselineInstrumentIds.length - 1);
    expect(evolvedInstrumentIds).not.toEqual(
      baselineInstrumentIds.filter((instrumentId) =>
        evolvedInstrumentIds.includes(instrumentId),
      ),
    );

    const baselineRouteIds =
      baseline.payload.registry_basis.certificate_class_routes.map(
        (route) => route.certificate_class,
      );
    const evolvedRouteIds =
      evolved.payload.registry_basis.certificate_class_routes.map(
        (route) => route.certificate_class,
      );
    expect(evolvedRouteIds).toHaveLength(baselineRouteIds.length - 1);
    expect(evolvedRouteIds).not.toEqual(
      baselineRouteIds.filter((routeId) => evolvedRouteIds.includes(routeId)),
    );

    expect(evolved.source.artifact_content_hash).not.toBe(
      baseline.source.artifact_content_hash,
    );
    expect(evolved.source_dependency_hash).not.toBe(
      baseline.source_dependency_hash,
    );
    expect(evolved.worker_validation_receipt_hash).not.toBe(
      baseline.worker_validation_receipt_hash,
    );
    expect(evolved.registry_projection_hash).not.toBe(
      baseline.registry_projection_hash,
    );
    expect(evolved.source.validation).toMatchObject({
      bound_artifact_content_hash: evolved.source.artifact_content_hash,
      bound_dependency_aggregate_identity: evolved.source_dependency_hash,
      issue_codes: [],
      registry_content_hash: evolved.registry_content_hash,
      registry_projection_hash: evolved.registry_projection_hash,
      source_payload_equal: true,
      status: "passed",
      worker_validation_receipt_hash: evolved.worker_validation_receipt_hash,
    });
    expect(evolved.payload.registry_content_hash).toBe(
      evolved.registry_content_hash,
    );

    await expect(
      admitConfidenceLedgerRiskSpendPacket(evolved),
    ).resolves.toEqual(evolved);
  });

  it("strictly admits each distinct non-available transport arm", async () => {
    const available = availablePacket();
    const blocked = {
      ...commonTransport(available),
      absence_reason: null,
      availability: "source_blocked",
      freshness: structuredClone(available.freshness),
      projection_hash: available.projection_hash,
      replay_address: available.replay_address,
      replay_pins: structuredClone(available.replay_pins),
      source_artifact_content_hash: available.source.artifact_content_hash,
      source_blocked_reason: "over_spend",
      source_dependency_hash: available.source_dependency_hash,
      source_rule_version: null,
      source_schema_version: available.source_schema_version,
      worker_validation_receipt_hash: available.worker_validation_receipt_hash,
      worker_validation_receipt_ref: available.worker_validation_receipt_ref,
    };
    await refreshTransportIdentity(blocked);
    const missing = {
      ...commonTransport(available),
      absence_reason: "governed confidence-ledger source is absent",
      availability: "artifact_missing",
      freshness: {
        basis: "request_observation",
        observed_at: available.as_of,
        source_as_of: null,
        state: "artifact_missing",
      },
      projection_hash: null,
      replay_address: null,
      replay_pins: null,
      source_artifact_content_hash: null,
      source_blocked_reason: null,
      source_dependency_hash: null,
      source_rule_version: null,
      source_schema_version: null,
      worker_validation_receipt_hash: null,
      worker_validation_receipt_ref: null,
    };
    const invalid = {
      ...commonTransport(available),
      absence_reason: "confidence-ledger source failed owner admission",
      availability: "invalid_source",
      freshness: {
        basis: "request_observation",
        observed_at: available.as_of,
        source_as_of: available.as_of,
        state: "invalid_source",
      },
      projection_hash: null,
      replay_address: null,
      replay_pins: null,
      source_artifact_content_hash: available.source.artifact_content_hash,
      source_blocked_reason: null,
      source_dependency_hash: null,
      source_rule_version: null,
      source_schema_version: available.source_schema_version,
      worker_validation_receipt_hash: null,
      worker_validation_receipt_ref: null,
    };

    await expect(
      admitConfidenceLedgerRiskSpendPacket(blocked),
    ).resolves.toMatchObject({
      availability: "source_blocked",
      source_blocked_reason: "over_spend",
    });
    await expect(
      admitConfidenceLedgerRiskSpendPacket(missing),
    ).resolves.toMatchObject({
      availability: "artifact_missing",
    });
    await expect(
      admitConfidenceLedgerRiskSpendPacket(invalid),
    ).resolves.toMatchObject({
      availability: "invalid_source",
    });
  });

  it.each([
    [
      "an undeclared root field",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        Object.assign(packet, { apparently_safe: true });
      },
    ],
    [
      "an undeclared amount field",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        Object.assign(packet.payload.scope_total_risk_spend.allocation, {
          display_hint: "safe",
        });
      },
    ],
    [
      "a second confidence scope",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.obligation_class_risk_spend[0].allocation.scope_id =
          "scope://other";
      },
    ],
    [
      "a cross-scope owner binding",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.obligation_class_risk_spend[0].spent.owner_scope_key =
          "owner://other";
      },
    ],
    [
      "a bare rational in place of a conditional amount",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.scope_total_risk_spend.allocation = {
          amount: { denominator: 1, numerator: 0 },
        } as never;
      },
    ],
    [
      "a missing valid-zero positive register",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        Reflect.deleteProperty(packet.payload, "positive_register");
      },
    ],
    [
      "a missing producer-referenced actual row",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.instrument_instances =
          packet.payload.instrument_instances.slice(1);
      },
    ],
  ])("rejects %s", async (_label, mutate) => {
    const packet = availablePacket();
    mutate(packet);

    await expect(admitConfidenceLedgerRiskSpendPacket(packet)).rejects.toThrow(
      /contract_error/iu,
    );
  });

  it.each([
    [
      "removed obligation row",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.obligation_class_risk_spend.pop();
      },
    ],
    [
      "reordered obligation rows",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        const rows = packet.payload.obligation_class_risk_spend;
        [rows[0], rows[1]] = [rows[1], rows[0]];
      },
    ],
    [
      "duplicated obligation row",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        const rows = packet.payload.obligation_class_risk_spend;
        rows[rows.length - 1] = structuredClone(rows[0]);
      },
    ],
    [
      "removed instrument definition",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.instrument_definitions.pop();
      },
    ],
    [
      "reordered instrument definitions",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        const rows = packet.payload.instrument_definitions;
        [rows[0], rows[1]] = [rows[1], rows[0]];
      },
    ],
    [
      "duplicated instrument definition",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        const rows = packet.payload.instrument_definitions;
        rows[rows.length - 1] = structuredClone(rows[0]);
      },
    ],
    [
      "removed certificate route",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.certificate_routes.pop();
      },
    ],
    [
      "reordered certificate routes",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        const rows = packet.payload.certificate_routes;
        [rows[0], rows[1]] = [rows[1], rows[0]];
      },
    ],
    [
      "duplicated certificate route",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        const rows = packet.payload.certificate_routes;
        rows[rows.length - 1] = structuredClone(rows[0]);
      },
    ],
  ])("rejects a one-sided %s", async (_label, mutate) => {
    const packet = availablePacket();
    mutate(packet);

    await expect(admitConfidenceLedgerRiskSpendPacket(packet)).rejects.toThrow(
      /contract_error.*denominator/iu,
    );
  });

  it("rejects a zero-spend semantic class outside the owner registry denominator", async () => {
    const packet = availablePacket();
    const zeroSpendCheck = packet.payload.semantic_ledger_basis.checks.find(
      (check) => check.spend.numerator === 0,
    );
    if (zeroSpendCheck === undefined) {
      throw new Error("fixture has no zero-spend semantic check");
    }
    zeroSpendCheck.obligation_class = "__unknown_obligation_class__" as never;

    await expect(admitConfidenceLedgerRiskSpendPacket(packet)).rejects.toThrow(
      /contract_error.*outside the owner registry denominator/iu,
    );
  });

  it("recomputes amount algebra instead of trusting displayed totals", async () => {
    const packet = availablePacket();
    packet.payload.scope_total_risk_spend.remaining.amount = {
      denominator: 1,
      numerator: 1,
    };

    await expect(admitConfidenceLedgerRiskSpendPacket(packet)).rejects.toThrow(
      /contract_error.*accounting/iu,
    );
  });

  it("rejects a self-rehashed derived row when its registry basis still disproves it", async () => {
    const packet = availablePacket();
    packet.payload.instrument_definitions[0].anytime_valid = false;
    await refreshSelfHashes(packet);

    await expect(admitConfidenceLedgerRiskSpendPacket(packet)).rejects.toThrow(
      /contract_error.*recursive basis/iu,
    );
  });

  it("rejects a coherently rehashed open-world envelope that contradicts the owner-derived negative arm", async () => {
    const packet = availablePacket();
    const envelope = packet.payload.coverage_envelope;
    envelope.search_basis_state = "governed_search_complete" as never;
    envelope.exclusion_basis_state = "approved" as never;
    envelope.review_state = "approved" as never;
    envelope.expiry_state = "active" as never;
    envelope.challenge_route_state = "appointed" as never;
    envelope.unknown_remainder = {
      cardinality: "0",
      kind: "none",
      probability: "0",
    } as never;
    await refreshEnvelopeAndAmountHashes(packet);

    await expect(admitConfidenceLedgerRiskSpendPacket(packet)).rejects.toThrow(
      /contract_error[\s\S]*coverage/iu,
    );
  });

  it("rejects a coherently rehashed available packet whose recomputed 1/50 spend exceeds delta 1/100", async () => {
    const packet = availablePacket();
    await forgeCoherentAvailableOverspend(packet);

    await expect(admitConfidenceLedgerRiskSpendPacket(packet)).rejects.toThrow(
      /contract_error.*available.*budget/iu,
    );
  });

  it.each([
    [
      "semantic-ledger schema version",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.semantic_ledger_basis.schema_version =
          "policyos.runtime.confidence_ledger.v999" as never;
      },
    ],
    [
      "conditionality clause",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.semantic_ledger_basis.conditionality_clause =
          "candidate-authored conditionality" as never;
      },
    ],
    [
      "good-event clause",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        packet.payload.semantic_ledger_basis.good_event_clause =
          "candidate-authored good event" as never;
        packet.payload.good_event_posture.good_event_clause =
          "candidate-authored good event";
      },
    ],
  ])(
    "blocks a coherently rehashed generated owner-literal substitution: %s",
    async (_label, mutate) => {
      const packet = availablePacket();
      mutate(packet);
      await refreshSemanticOwnerHashes(packet);

      await expect(
        evaluateConfidenceLedgerProtectedQuery({
          evaluationMode: "exact_finite_schema",
          packetCandidate: packet,
          rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
          stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
        }),
      ).resolves.toEqual({
        reason: "parser_or_schema_failure",
        status: "blocked",
      });
    },
  );

  it("vetoes aggregate promotion for each load-bearing negative posture", () => {
    const baseline = availablePacket();
    expect(confidenceLedgerPromotionBlockers(baseline)).toEqual(
      expect.arrayContaining([
        "coverage:open_world_unresolved",
        "appointment:institutional_authority_unappointed",
      ]),
    );

    const rowBlocked = availablePacket();
    rowBlocked.payload.instrument_blockers = ["non_anytime_valid"];
    expect(confidenceLedgerPromotionBlockers(rowBlocked)).toContain(
      "instrument:non_anytime_valid",
    );
    expect(confidenceLedgerPromotionBlockers(baseline)).toContain(
      "definition:owner_verified_confidence_sequence:owner_theorem_unavailable",
    );
    expect(confidenceLedgerPromotionBlockers(baseline)).toContain(
      "route:n8_fixed_time_calibration_candidate:non_anytime_valid",
    );

    const overspent = availablePacket();
    overspent.payload.budget_posture = "over_spend";
    expect(confidenceLedgerPromotionBlockers(overspent)).toContain(
      "budget:over_spend",
    );
  });
});

describe("confidence-ledger shared protected-query evaluator", () => {
  it("derives one exact receipt from independently admitted candidate and captured bytes", async () => {
    const packet = availablePacket();
    const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));

    const result = await evaluateConfidenceLedgerProtectedQuery({
      evaluationMode: "exact_finite_schema",
      packetCandidate: packet,
      rawPacketBytes,
      stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
    });

    expect(result.status).toBe("exact");
    if (result.status !== "exact") return;
    expect(result.packet).toEqual(packet);
    const capturedCopy = result.capturedResponseBytes.copy();
    expect(capturedCopy.byteLength).toBe(rawPacketBytes.byteLength);
    expect(
      capturedCopy.every((byte, index) => byte === rawPacketBytes[index]),
    ).toBe(true);
    expect(result.capturedResponseBytes.copy()).not.toBe(
      result.capturedResponseBytes.copy(),
    );
    expect(result.receipt.observation_basis).toBe(
      "candidate_and_captured_bytes_independently_admitted",
    );
    expect(Object.keys(result.protectedQueries)).toEqual(
      CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
    );
  });

  it("owns the transport bytes synchronously and exposes only fresh copies", async () => {
    const packet = availablePacket();
    const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));
    const entrySnapshot = new Uint8Array(rawPacketBytes);

    const pending = evaluateConfidenceLedgerProtectedQuery({
      evaluationMode: "exact_finite_schema",
      packetCandidate: packet,
      rawPacketBytes,
      stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
    });
    queueMicrotask(() => rawPacketBytes.fill(0x5a));
    rawPacketBytes.fill(0xa5);

    const result = await pending;
    expect(result.status).toBe("exact");
    if (result.status !== "exact") return;
    const firstCopy = result.capturedResponseBytes.copy();
    expect(firstCopy).toEqual(entrySnapshot);
    firstCopy.fill(0xff);
    expect(result.capturedResponseBytes.copy()).toEqual(entrySnapshot);
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, 1.5, 0, -1, 64])(
    "blocks an invalid or exhausted finite budget %s before admitting bytes",
    async (stepBudget) => {
      const packet = availablePacket();
      const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));

      await expect(
        evaluateConfidenceLedgerProtectedQuery({
          evaluationMode: "exact_finite_schema",
          packetCandidate: packet,
          rawPacketBytes,
          stepBudget,
        }),
      ).resolves.toEqual({ status: "blocked", reason: "timeout" });
    },
  );

  it("derives an empty consistency set when two valid transport observations disagree", async () => {
    const packet = availablePacket();
    const capturedPacket = structuredClone(packet);
    capturedPacket.freshness.observed_at = "2026-02-11T12:00:01Z";
    const rawPacketBytes = new TextEncoder().encode(
      JSON.stringify(capturedPacket),
    );

    await expect(
      evaluateConfidenceLedgerProtectedQuery({
        evaluationMode: "exact_finite_schema",
        packetCandidate: packet,
        rawPacketBytes,
        stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "empty_consistency_set",
    });
  });

  it("blocks oversized candidate text work before schema admission", async () => {
    const packet = availablePacket();
    const oversizedCandidate = {
      ...packet,
      evaluator_padding: "x".repeat(262_145),
    };

    await expect(
      evaluateConfidenceLedgerProtectedQuery({
        evaluationMode: "exact_finite_schema",
        packetCandidate: oversizedCandidate,
        rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
        stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
      }),
    ).resolves.toEqual({
      reason: "unsupported_or_out_of_model",
      status: "blocked",
    });
  });

  it("blocks the 151866-byte reviewer denominator before exact decimal work", async () => {
    const packet = availablePacket();
    packet.payload.semantic_ledger_basis.checks[0].spend.denominator = 1_000_171;
    await refreshSemanticOwnerHashes(packet);
    const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));
    expect(rawPacketBytes.byteLength).toBe(151_866);

    await expect(
      evaluateConfidenceLedgerProtectedQuery({
        evaluationMode: "exact_finite_schema",
        packetCandidate: packet,
        rawPacketBytes,
        stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
      }),
    ).resolves.toEqual({
      reason: "unsupported_or_out_of_model",
      status: "blocked",
    });
    await expect(admitConfidenceLedgerRiskSpendPacket(packet)).rejects.toThrow(
      /contract_error.*arithmetic.*denominator/iu,
    );
  });

  it("caps aggregate rational work across all 98 values before admission", async () => {
    const packet = availablePacket();
    expect(replaceEveryRationalDenominator(packet, 3_000)).toBe(98);

    await expect(admitConfidenceLedgerRiskSpendPacket(packet)).rejects.toThrow(
      /contract_error.*aggregate rational work/iu,
    );
  });

  it("debits both independently observed near-cap rational workloads", async () => {
    const packet = availablePacket();
    packet.payload.semantic_ledger_basis.checks[0].spend.denominator = 100_000;
    const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));

    await expect(
      evaluateConfidenceLedgerProtectedQuery({
        evaluationMode: "exact_finite_schema",
        packetCandidate: packet,
        rawPacketBytes,
        // Fits either observation alone, but not both complete arithmetic debits.
        stepBudget: 960_000,
      }),
    ).resolves.toEqual({ reason: "timeout", status: "blocked" });
  });

  it.each([
    ["missing_input_or_incomplete_history", null, new Uint8Array()],
    [
      "parser_or_schema_failure",
      availablePacket(),
      new TextEncoder().encode("{}"),
    ],
    [
      "unsupported_or_out_of_model",
      {
        ...availablePacket(),
        packet_schema_version:
          "policyos.runtime.confidence_ledger_risk_spend_packet.v2",
      },
      new TextEncoder().encode(JSON.stringify(availablePacket())),
    ],
  ])(
    "returns the closed %s blocker from real evaluator inputs",
    async (reason, packetCandidate, rawPacketBytes) => {
      await expect(
        evaluateConfidenceLedgerProtectedQuery({
          evaluationMode: "exact_finite_schema",
          packetCandidate,
          rawPacketBytes: rawPacketBytes as Uint8Array,
          stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
        }),
      ).resolves.toEqual({ status: "blocked", reason });
    },
  );

  it("blocks a sampled evaluator mode as an unproved approximation", async () => {
    const packet = availablePacket();
    await expect(
      evaluateConfidenceLedgerProtectedQuery({
        evaluationMode: "sampled_search",
        packetCandidate: packet,
        rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
        stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "unproved_approximation",
    });
  });
});
