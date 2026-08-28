import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

type JsonObject = Record<string, unknown>;

export const EPOCH_PERTURBATION_CLASSES = [
  "incident",
  "appeal",
  "correction",
  "retraction",
  "legal_change",
  "discovered_bias",
] as const;

function clone<T>(value: T): T {
  return structuredClone(value);
}

function object(value: unknown): JsonObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("epoch staleness fixture expected an object");
  }
  return value as JsonObject;
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (typeof value === "object" && value !== null) {
    const record = value as JsonObject;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export function epochProjection(candidate: JsonObject): JsonObject {
  return object(candidate.projection);
}

export function withServerSemanticHash(candidate: JsonObject): JsonObject {
  const copied = clone(candidate);
  const projection = epochProjection(copied);
  const semanticProjection = clone(projection);
  delete semanticProjection.observed_at;
  delete semanticProjection.projection_semantic_hash;
  const framed = Buffer.concat([
    Buffer.from("polisyos.runtime.epoch-staleness.semantic.v1\0", "utf8"),
    Buffer.from(canonicalJson(semanticProjection), "utf8"),
  ]);
  projection.projection_semantic_hash = `sha256:${createHash("sha256")
    .update(framed)
    .digest("hex")}`;
  return copied;
}

function epochStalenessExample(name: string): JsonObject {
  const schema = JSON.parse(
    readFileSync(
      resolve(process.cwd(), "../../schemas/runtime_api_v1.openapi.json"),
      "utf8",
    ),
  ) as JsonObject;
  const paths = object(schema.paths);
  const route = object(paths["/api/v1/temporal/runs/{run_id}/epoch-staleness"]);
  const operation = object(route.get);
  const responses = object(operation.responses);
  const success = object(responses["200"]);
  const content = object(success.content);
  const media = object(content["application/json"]);
  const examples = object(media.examples);
  const example = object(examples[name]);
  return clone(object(example.value));
}

export function epochStalenessAbsenceFixture(): JsonObject {
  return epochStalenessExample("declared_production_absence");
}

export function epochStalenessPositiveFixture(): JsonObject {
  return epochStalenessExample("positive_fixture_only");
}

export function epochStalenessSixClassFixture(): JsonObject {
  const candidate = epochStalenessAbsenceFixture();
  const projection = epochProjection(candidate);
  projection.perturbations = EPOCH_PERTURBATION_CLASSES.map(
    (sourceClass, index) => {
      const eventDigit = ((index + 1) % 10).toString();
      const targetDigit = ((index + 4) % 10).toString();
      return {
        adjudicated_disposition:
          sourceClass === "incident" ? "annotation_only" : "review_required",
        advisory_posture:
          sourceClass === "incident" ? "annotation_only" : "review_required",
        event_ref: {
          artifact_id: `sha256:${eventDigit.repeat(64)}`,
          kind: `governance.${sourceClass}`,
          media_type: "application/json",
        },
        observed_at: `2026-02-${String(index + 12).padStart(2, "0")}T12:00:00Z`,
        owner_evidence_refs: [],
        scope: sourceClass === "appeal" ? "instance" : "dependency_descendants",
        source_class: sourceClass,
        source_evidence_refs: [],
        target_ref: {
          artifact_id: `sha256:${targetDigit.repeat(64)}`,
          kind: "scientist.decision_packet",
          media_type: "application/json",
        },
      };
    },
  );
  return withServerSemanticHash(candidate);
}
