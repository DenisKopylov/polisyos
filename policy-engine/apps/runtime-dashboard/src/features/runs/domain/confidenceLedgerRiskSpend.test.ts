import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";

import {
  admitConfidenceLedgerRiskSpendPacket,
  confidenceLedgerPromotionBlockers,
  orderedConfidenceLedgerActualRows,
} from "./confidenceLedgerRiskSpend";

function availablePacket(): AvailableConfidenceLedgerRiskSpendPacket {
  const openApi = JSON.parse(
    readFileSync(
      resolve(process.cwd(), "../../schemas/runtime_api_v1.openapi.json"),
      "utf8",
    ),
  ) as {
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
      "a reordered obligation denominator",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        const rows = packet.payload.obligation_class_risk_spend;
        [rows[0], rows[1]] = [rows[1], rows[0]];
      },
    ],
    [
      "a reordered instrument denominator",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        const rows = packet.payload.instrument_definitions;
        [rows[0], rows[1]] = [rows[1], rows[0]];
      },
    ],
    [
      "a reordered route denominator",
      (packet: AvailableConfidenceLedgerRiskSpendPacket) => {
        const rows = packet.payload.certificate_routes;
        [rows[0], rows[1]] = [rows[1], rows[0]];
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
