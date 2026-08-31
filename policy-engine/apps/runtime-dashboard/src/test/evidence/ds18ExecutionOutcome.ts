import { createHash } from "node:crypto";

import { z } from "zod";

/** Maximum raw bytes admitted from each canonical-checker stream. */
export const DS18_MAX_STREAM_BYTES = 8_388_608;

const sha256 = z.string().regex(/^sha256:[0-9a-f]{64}$/u);
const byteCount = z.number().int().min(0).max(DS18_MAX_STREAM_BYTES);

export const ds18TimeSemanticsCoverageProjectionSchema = z
  .object({
    predicate_provenance: z.literal("independently_reconciled"),
    source_file_count: z.number().int().positive(),
    root_count: z.number().int().positive(),
    obligated_root_count: z.number().int().positive(),
    covered_root_count: z.number().int().nonnegative(),
  })
  .strict()
  .superRefine((projection, context) => {
    if (projection.obligated_root_count > projection.root_count) {
      context.addIssue({
        code: "custom",
        path: ["obligated_root_count"],
        message: "obligated roots cannot exceed reconciled roots",
      });
    }
    if (projection.covered_root_count > projection.obligated_root_count) {
      context.addIssue({
        code: "custom",
        path: ["covered_root_count"],
        message: "covered roots cannot exceed obligated roots",
      });
    }
  });

const notEstablishedErrorCodeSchema = z.enum([
  "checker_exit_nonzero",
  "stdout_too_large",
  "stderr_too_large",
  "stdout_invalid_utf8",
  "stdout_invalid_json",
  "stdout_invalid_packet",
]);

const establishedOutcomeSchema = z
  .object({
    kind: z.literal("established"),
    projection: ds18TimeSemanticsCoverageProjectionSchema,
  })
  .strict();

const notEstablishedOutcomeSchema = z
  .object({
    kind: z.literal("not_established"),
    error_code: notEstablishedErrorCodeSchema,
    exit_code: z.number().int().nonnegative(),
    stdout_byte_count: byteCount,
    stdout_sha256: sha256,
    stderr_byte_count: byteCount,
    stderr_sha256: sha256,
  })
  .strict();

/** Strict, raw-evidence-preserving result of one DS18 coverage invocation. */
export const ds18ExecutionOutcomeSchema = z.discriminatedUnion("kind", [
  establishedOutcomeSchema,
  notEstablishedOutcomeSchema,
]);

export type Ds18ExecutionOutcome = z.infer<typeof ds18ExecutionOutcomeSchema>;
export type Ds18ExecutionFailureCode = z.infer<
  typeof notEstablishedErrorCodeSchema
>;

export interface Ds18ExecutionCapture {
  readonly exitCode: number;
  readonly stdout: Uint8Array;
  readonly stderr: Uint8Array;
}

function rawDigest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function nonEstablished(
  errorCode: Ds18ExecutionFailureCode,
  capture: Ds18ExecutionCapture,
): Ds18ExecutionOutcome {
  return notEstablishedOutcomeSchema.parse({
    kind: "not_established",
    error_code: errorCode,
    exit_code: capture.exitCode,
    stdout_byte_count: Math.min(
      capture.stdout.byteLength,
      DS18_MAX_STREAM_BYTES,
    ),
    stdout_sha256: rawDigest(capture.stdout),
    stderr_byte_count: Math.min(
      capture.stderr.byteLength,
      DS18_MAX_STREAM_BYTES,
    ),
    stderr_sha256: rawDigest(capture.stderr),
  });
}

/**
 * Admit a raw canonical-checker invocation without normalizing either stream.
 *
 * A nonzero exit is terminal before decoding stdout: the bounded byte evidence
 * remains inspectable without elevating diagnostic text into an admitted claim.
 */
export function decodeDs18ExecutionOutcome(
  capture: Ds18ExecutionCapture,
): Ds18ExecutionOutcome {
  if (capture.stdout.byteLength > DS18_MAX_STREAM_BYTES) {
    return nonEstablished("stdout_too_large", capture);
  }
  if (capture.stderr.byteLength > DS18_MAX_STREAM_BYTES) {
    return nonEstablished("stderr_too_large", capture);
  }
  if (capture.exitCode !== 0) {
    return nonEstablished("checker_exit_nonzero", capture);
  }

  let stdout: string;
  try {
    stdout = new TextDecoder("utf-8", { fatal: true }).decode(capture.stdout);
  } catch {
    return nonEstablished("stdout_invalid_utf8", capture);
  }

  let packet: unknown;
  try {
    packet = JSON.parse(stdout);
  } catch {
    return nonEstablished("stdout_invalid_json", capture);
  }

  const projection = ds18TimeSemanticsCoverageProjectionSchema.safeParse(packet);
  if (!projection.success) {
    return nonEstablished("stdout_invalid_packet", capture);
  }
  return establishedOutcomeSchema.parse({
    kind: "established",
    projection: projection.data,
  });
}

/** Dynamic primitive-adoption fields derived solely from an admitted DS18 outcome. */
export function primitiveAdoptionFromDs18Coverage(outcome: Ds18ExecutionOutcome) {
  if (outcome.kind === "not_established") {
    return {
      scope_description:
        "The current decision-bearing render-root denominator failed its recomputing DS18 coverage check.",
      predicate_provenance: "not_established" as const,
      limitation: `The DS18 execution outcome is not established (${outcome.error_code}).`,
      measurement: {
        kind: "unknown" as const,
        reason_code: "time_semantics_coverage_not_established" as const,
        predicate_provenance: "not_established" as const,
      },
      known_facts: {
        source_file_count: 0,
        render_root_count: 0,
        obligated_root_count: 0,
      },
    };
  }

  const { projection } = outcome;
  return {
    scope_description: `All ${String(projection.obligated_root_count)} independently reconciled decision-bearing or inherited render/export roots in ${String(projection.source_file_count)} production TypeScript files.`,
    predicate_provenance: "recomputed" as const,
    limitation:
      "This measures complete DS18 composition at its source freeze; it does not grant policy or design authority.",
    measurement:
      projection.covered_root_count === 0
        ? {
            kind: "zero" as const,
            reason_code: "observed_zero" as const,
            numerator: 0 as const,
            denominator: projection.obligated_root_count,
            ratio: 0 as const,
            ranking: null,
          }
        : {
            kind: "measured" as const,
            reason_code: "observed_ratio" as const,
            numerator: projection.covered_root_count,
            denominator: projection.obligated_root_count,
            ratio:
              projection.covered_root_count / projection.obligated_root_count,
            ranking: null,
          },
    known_facts: {
      source_file_count: projection.source_file_count,
      render_root_count: projection.root_count,
      obligated_root_count: projection.obligated_root_count,
    },
  };
}
