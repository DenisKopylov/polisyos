import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { z } from "zod";

import {
  ATLAS_HONESTY_COMPREHENSION_PROTOCOL,
  ATLAS_HONESTY_METRIC_IDS,
} from "./atlasHonestyComprehensionProtocol";

export const ATLAS_HEALTH_METRIC_REPORT_SCHEMA = {
  id: "polisyos.atlas.health-metric-report",
  version: "1.0.0",
} as const;

export const ATLAS_HEALTH_METRIC_SNAPSHOT_SCHEMA = {
  id: "polisyos.atlas.health-metric-snapshot",
  version: "1.0.0",
} as const;

export const ATLAS_HEALTH_METRIC_PERSISTENCE_OPERATION =
  "persist_atlas_health_metrics" as const;

export const ATLAS_HEALTH_METRIC_IDS = [
  "primitive_adoption",
  "fail_closed_fidelity",
  "audience_enforcement",
  "surface_missing_closure",
  "evidence_coverage",
  "machine_twin_parity",
  "honesty_comprehension",
] as const;

const HEALTH_PRODUCER_ID = "polisyos.atlas.health_metric_instrument";
const HEALTH_PRODUCER_VERSION = "1.0.0";
const HEALTH_PRODUCER_SCRIPT =
  "apps/runtime-dashboard/scripts/measure_atlas_health.mjs";
const HEALTH_PRODUCER_SOURCE =
  "apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts";
const HEALTH_SOURCE_VALIDATOR =
  "apps/runtime-dashboard/scripts/validate_atlas_health_sources.py";
const HONESTY_PROTOCOL_SOURCE =
  "apps/runtime-dashboard/src/test/evidence/atlasHonestyComprehensionProtocol.ts";

const nonEmptyString = z
  .string()
  .min(1)
  .refine((value) => value.trim() === value, {
    message: "value must have no surrounding whitespace",
  });
const identity = nonEmptyString.regex(/^[a-z0-9][a-z0-9._:@/-]*$/u);
const sha256 = z.string().regex(/^[0-9a-f]{64}$/u);
const artifactId = z.string().regex(/^sha256:[0-9a-f]{64}$/u);
const repositoryRevision = z.string().regex(/^[0-9a-f]{40}$/u);
const utcTimestamp = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u)
  .refine((value) => new Date(value).toISOString() === value, {
    message: "timestamp must be a real millisecond-precision UTC instant",
  });

const sourceRefSchema = z
  .object({
    path: nonEmptyString,
    sha256,
    role: nonEmptyString,
  })
  .strict();

const observedBasisSchema = z
  .object({
    kind: z.literal("observed_by_instrument"),
    producer_id: z.literal(HEALTH_PRODUCER_ID),
    producer_version: z.literal(HEALTH_PRODUCER_VERSION),
    predicate_provenance: z.enum(["recomputed", "not_established"]),
    source_refs: z.array(sourceRefSchema).min(1),
    limitation: nonEmptyString.nullable(),
  })
  .strict();

const unknownMeasurementSchema = z
  .object({
    kind: z.literal("unknown"),
    reason_code: identity,
    predicate_provenance: z.literal("not_established"),
  })
  .strict();

const zeroMeasurementSchema = z
  .object({
    kind: z.literal("zero"),
    reason_code: z.literal("observed_zero"),
    numerator: z.literal(0),
    denominator: z.number().int().positive(),
    ratio: z.literal(0),
    ranking: z.null(),
  })
  .strict();

const missingMeasurementSchema = z
  .object({
    kind: z.literal("missing"),
    reason_code: identity,
    expected_owner_ref: nonEmptyString,
    ranking: z.null(),
  })
  .strict();

const incomparableMeasurementSchema = z
  .object({
    kind: z.literal("incomparable"),
    reason_code: z.enum(["zero_denominator", "no_admissible_ranking"]),
    numerator: z.number().int().nonnegative(),
    denominator: z.literal(0),
    ratio: z.null(),
    ranking: z.null(),
    scope_refs: z.array(nonEmptyString).min(1),
  })
  .strict();

const measuredMeasurementSchema = z
  .object({
    kind: z.literal("measured"),
    reason_code: z.literal("observed_ratio"),
    numerator: z.number().int().nonnegative(),
    denominator: z.number().int().positive(),
    ratio: z.number().min(0).max(1),
    ranking: z.null(),
  })
  .strict()
  .superRefine((measurement, context) => {
    if (measurement.numerator > measurement.denominator) {
      context.addIssue({
        code: "custom",
        path: ["numerator"],
        message: "metric numerator cannot exceed its complete denominator",
      });
    }
    if (measurement.ratio !== measurement.numerator / measurement.denominator) {
      context.addIssue({
        code: "custom",
        path: ["ratio"],
        message: "metric ratio must be derived from numerator and denominator",
      });
    }
  });

const scopeSchema = z
  .object({
    scope_id: identity,
    description: nonEmptyString,
  })
  .strict();

const thresholdSchema = z
  .object({
    metric_id: identity,
    status: z.literal("not_established"),
    comparator: z.null(),
    value: z.null(),
    unit: z.null(),
    source_ref: z.null(),
  })
  .strict();

const noThresholdsSchema = z.tuple([]);
const count = z.number().int().nonnegative();

function observedBasisFor(
  predicateProvenance: "recomputed" | "not_established",
) {
  return observedBasisSchema.extend({
    predicate_provenance: z.literal(predicateProvenance),
  });
}

const notEstablishedBasisSchema = observedBasisFor("not_established");
const recomputedBasisSchema = observedBasisFor("recomputed");

const primitiveAdoptionRowSchema = z
  .object({
    metric_id: z.literal("primitive_adoption"),
    instrumentation_status: z.literal("instrumented"),
    definition: nonEmptyString,
    honest_direction: nonEmptyString,
    scope: scopeSchema.extend({
      scope_id: z.literal("ds1-live-readiness-rows"),
    }),
    basis: notEstablishedBasisSchema,
    measurement: unknownMeasurementSchema.extend({
      reason_code: z.literal("primitive_relation_not_established"),
    }),
    known_facts: z.object({ readiness_entry_count: count }).strict(),
    thresholds: noThresholdsSchema,
  })
  .strict();

const failClosedFidelityRowSchema = z
  .object({
    metric_id: z.literal("fail_closed_fidelity"),
    instrumentation_status: z.literal("instrumented"),
    definition: nonEmptyString,
    honest_direction: nonEmptyString,
    scope: scopeSchema.extend({
      scope_id: z.literal("ds1-live-readiness-rows"),
    }),
    basis: notEstablishedBasisSchema,
    measurement: unknownMeasurementSchema.extend({
      reason_code: z.literal("render_state_denominator_not_established"),
    }),
    known_facts: z.object({ readiness_entry_count: count }).strict(),
    thresholds: noThresholdsSchema,
  })
  .strict();

const audienceEnforcementRowSchema = z
  .object({
    metric_id: z.literal("audience_enforcement"),
    instrumentation_status: z.literal("instrumented"),
    definition: nonEmptyString,
    honest_direction: nonEmptyString,
    scope: scopeSchema.extend({
      scope_id: z.literal("server-audience-denial-proxies"),
    }),
    basis: notEstablishedBasisSchema,
    measurement: unknownMeasurementSchema.extend({
      reason_code: z.literal("audience_endpoint_denominator_not_established"),
    }),
    known_facts: z.object({ proxy_test_count: count }).strict(),
    thresholds: noThresholdsSchema,
  })
  .strict();

const surfaceMissingClosureRowSchema = z
  .object({
    metric_id: z.literal("surface_missing_closure"),
    instrumentation_status: z.literal("instrumented"),
    definition: nonEmptyString,
    honest_direction: nonEmptyString,
    scope: scopeSchema.extend({
      scope_id: z.literal("policy-design-case-cluster-map-cells"),
    }),
    basis: recomputedBasisSchema,
    measurement: z.union([zeroMeasurementSchema, measuredMeasurementSchema]),
    known_facts: z
      .object({
        cell_count: z.number().int().positive(),
        implemented_cell_count: count,
        surface_missing_count: count,
        implemented_but_not_orchestrated_count: count,
        open_or_incomplete_count: count,
        open_cell_count: count,
        closure_contract_count: count,
      })
      .strict(),
    thresholds: noThresholdsSchema,
  })
  .strict()
  .superRefine((row, context) => {
    if (row.measurement.denominator !== row.known_facts.cell_count) {
      context.addIssue({
        code: "custom",
        path: ["measurement", "denominator"],
        message:
          "surface closure denominator must bind the complete cell count",
      });
    }
    const targetStateCount =
      row.known_facts.surface_missing_count +
      row.known_facts.implemented_but_not_orchestrated_count;
    if (row.measurement.numerator !== targetStateCount) {
      context.addIssue({
        code: "custom",
        path: ["measurement", "numerator"],
        message:
          "surface closure numerator must bind only the two target state counts",
      });
    }
  });

const evidenceCoverageRowSchema = z
  .object({
    metric_id: z.literal("evidence_coverage"),
    instrumentation_status: z.literal("instrumented"),
    definition: nonEmptyString,
    honest_direction: nonEmptyString,
    scope: scopeSchema.extend({
      scope_id: z.literal("ds2-adoption-ledger-stable-components"),
    }),
    basis: recomputedBasisSchema,
    measurement: z.union([
      incomparableMeasurementSchema.extend({
        reason_code: z.literal("zero_denominator"),
      }),
      zeroMeasurementSchema,
      measuredMeasurementSchema,
    ]),
    known_facts: z
      .object({
        adoption_entry_count: count,
        stable_component_count: count,
        stable_with_browser_and_at_count: count,
      })
      .strict(),
    thresholds: noThresholdsSchema,
  })
  .strict()
  .superRefine((row, context) => {
    if (
      row.measurement.denominator !== row.known_facts.stable_component_count
    ) {
      context.addIssue({
        code: "custom",
        path: ["measurement", "denominator"],
        message: "evidence denominator must bind the stable component count",
      });
    }
    if (
      row.measurement.numerator !==
      row.known_facts.stable_with_browser_and_at_count
    ) {
      context.addIssue({
        code: "custom",
        path: ["measurement", "numerator"],
        message: "evidence numerator must bind schema-valid stable evidence",
      });
    }
  });

const machineTwinParityRowSchema = z
  .object({
    metric_id: z.literal("machine_twin_parity"),
    instrumentation_status: z.literal("instrumented"),
    definition: nonEmptyString,
    honest_direction: nonEmptyString,
    scope: scopeSchema.extend({
      scope_id: z.literal("ds1-live-readiness-rows"),
    }),
    basis: notEstablishedBasisSchema,
    measurement: missingMeasurementSchema.extend({
      reason_code: z.literal("machine_twin_relation_missing"),
      expected_owner_ref: z.literal(
        "atlas.surface-machine-twin-relation@not_present",
      ),
    }),
    known_facts: z
      .object({
        readiness_entry_count: count,
        machine_audience_count: count,
        implemented_entry_count: count,
      })
      .strict(),
    thresholds: noThresholdsSchema,
  })
  .strict();

const honestyComprehensionRowSchema = z
  .object({
    metric_id: z.literal("honesty_comprehension"),
    instrumentation_status: z.literal("protocol_seam_only"),
    definition: nonEmptyString,
    honest_direction: nonEmptyString,
    scope: scopeSchema.extend({
      scope_id: z.literal("ds6-honesty-comprehension-seed"),
    }),
    basis: notEstablishedBasisSchema,
    measurement: missingMeasurementSchema.extend({
      reason_code: z.literal("honesty_observation_missing"),
      expected_owner_ref: z.literal(
        "INT-R3/research-observation@not_established",
      ),
    }),
    known_facts: z
      .object({
        task_count: count,
        metric_count: z.literal(6),
        research_input_status: z.literal("not_established"),
        benchmark_status: z.literal("not_established"),
      })
      .strict(),
    thresholds: z.array(thresholdSchema),
  })
  .strict();

const metricRowsSchema = z.tuple([
  primitiveAdoptionRowSchema,
  failClosedFidelityRowSchema,
  audienceEnforcementRowSchema,
  surfaceMissingClosureRowSchema,
  evidenceCoverageRowSchema,
  machineTwinParityRowSchema,
  honestyComprehensionRowSchema,
]);

const reportSchemaIdentity = z
  .object({
    id: z.literal(ATLAS_HEALTH_METRIC_REPORT_SCHEMA.id),
    version: z.literal(ATLAS_HEALTH_METRIC_REPORT_SCHEMA.version),
  })
  .strict();

const producerSchema = z
  .object({
    producer_id: z.literal(HEALTH_PRODUCER_ID),
    producer_version: z.literal(HEALTH_PRODUCER_VERSION),
    fixed_script: z.literal(HEALTH_PRODUCER_SCRIPT),
    repository_revision: repositoryRevision,
    repository_dirty: z.boolean(),
    implementation_refs: z.tuple([
      sourceRefSchema,
      sourceRefSchema,
      sourceRefSchema,
    ]),
  })
  .strict()
  .superRefine((producer, context) => {
    const paths = producer.implementation_refs.map((ref) => ref.path);
    if (
      JSON.stringify(paths) !==
      JSON.stringify([
        HEALTH_PRODUCER_SOURCE,
        HEALTH_PRODUCER_SCRIPT,
        HEALTH_SOURCE_VALIDATOR,
      ])
    ) {
      context.addIssue({
        code: "custom",
        path: ["implementation_refs"],
        message:
          "producer implementation refs must cover the typed owner, launcher, and canonical-source validator",
      });
    }
  });

const interpretationSchema = z
  .object({
    posture: z.literal("candidate_only"),
    aggregate_status: z.null(),
    aggregate_ranking: z.null(),
    grants_stable: z.literal(false),
    blocking_permitted: z.literal(false),
  })
  .strict();

const candidateAuthoritySchema = z
  .object({
    classification: z.literal("candidate_only"),
    authoritative_for: z.tuple([]),
    may_not_use_for: z.tuple([
      z.literal("descriptive_atlas_health_measurement"),
      z.literal("component_maturity"),
      z.literal("design_authority"),
      z.literal("policy_authority"),
      z.literal("promotion"),
      z.literal("publication"),
      z.literal("runtime_authority"),
      z.literal("stable"),
    ]),
  })
  .strict();

const EXPECTED_BASIS_REFS = [
  [
    [
      "architecture/atlas_surfaces/live-application-readiness-ledger.json",
      "complete_readiness_population",
    ],
    [
      "architecture/atlas_surfaces/surface-readiness-ledger.schema.json",
      "readiness_owner_schema",
    ],
  ],
  [
    [
      "architecture/atlas_surfaces/live-application-readiness-ledger.json",
      "complete_readiness_population",
    ],
    [
      "architecture/atlas_surfaces/surface-readiness-ledger.schema.json",
      "readiness_owner_schema",
    ],
  ],
  [
    [
      "tests/unit/runtime/http/test_authorization_audience_denials.py",
      "incomplete_server_denial_proxy_set",
    ],
  ],
  [
    [
      "architecture/policy_design_case/cluster_ownership_map.toml",
      "complete_cluster_map_owner",
    ],
    [
      "architecture/policy_design_case/inventory.json",
      "cluster_inventory_dependency",
    ],
    [
      "architecture/policy_design_case/capability_reality_report.json",
      "capability_ratchet_dependency",
    ],
    [
      "docs/reference/policy-design-case-failure-patterns.md",
      "failure_vocabulary_dependency",
    ],
    [
      "tools/quality/validation/check_policy_design_case_cluster_ownership_map.py",
      "subordinate_recomputation",
    ],
  ],
  [
    [
      "architecture/atlas_surfaces/atlas-v15-adoption-ledger.json",
      "complete_component_maturity_population",
    ],
    [
      "architecture/atlas_surfaces/adoption-ledger.schema.json",
      "adoption_owner_schema",
    ],
    [
      "architecture/atlas_surfaces/surface-readiness-ledger.schema.json",
      "adoption_external_schema_dependency",
    ],
  ],
  [
    [
      "architecture/atlas_surfaces/live-application-readiness-ledger.json",
      "complete_readiness_population",
    ],
    [
      "architecture/atlas_surfaces/surface-readiness-ledger.schema.json",
      "readiness_owner_schema",
    ],
  ],
  [
    [
      "apps/runtime-dashboard/src/test/evidence/atlasHonestyComprehensionProtocol.ts",
      "c12_instrument_and_int_r3_seam",
    ],
  ],
] as const;

export const atlasHealthMetricReportSchema = z
  .object({
    report_schema: reportSchemaIdentity,
    producer: producerSchema,
    measured_at: utcTimestamp,
    measurements: metricRowsSchema,
    interpretation: interpretationSchema,
    authority: candidateAuthoritySchema,
  })
  .strict()
  .superRefine((report, context) => {
    const honesty = report.measurements[6];
    const expectedThresholds = ATLAS_HONESTY_METRIC_IDS.map((metric_id) => ({
      metric_id,
      status: "not_established",
      comparator: null,
      value: null,
      unit: null,
      source_ref: null,
    }));
    if (
      JSON.stringify(honesty.thresholds) !== JSON.stringify(expectedThresholds)
    ) {
      context.addIssue({
        code: "custom",
        path: ["measurements", 6, "thresholds"],
        message: "honesty thresholds must exactly preserve the C12 INT-R3 seam",
      });
    }
    report.measurements.slice(0, 6).forEach((row, index) => {
      if (row.thresholds.length !== 0) {
        context.addIssue({
          code: "custom",
          path: ["measurements", index, "thresholds"],
          message: "C11 does not invent a threshold for an instrumented metric",
        });
      }
    });
    report.measurements.forEach((row, index) => {
      const actualRefs = row.basis.source_refs.map(
        ({ path: filePath, role }) => [filePath, role],
      );
      const expectedRefs = EXPECTED_BASIS_REFS[index];
      if (JSON.stringify(actualRefs) !== JSON.stringify(expectedRefs)) {
        context.addIssue({
          code: "custom",
          path: ["measurements", index, "basis", "source_refs"],
          message: "metric basis refs must bind the exact canonical owner set",
        });
      }
    });
  });

export type AtlasHealthMetricReport = z.infer<
  typeof atlasHealthMetricReportSchema
>;
export type AtlasHealthMetricRow =
  AtlasHealthMetricReport["measurements"][number];

const healthSourceProjectionSchema = z
  .object({
    projection_schema: z
      .object({
        id: z.literal("polisyos.atlas.health-source-projection"),
        version: z.literal("1.0.0"),
      })
      .strict(),
    producer: z
      .object({
        producer_id: z.literal("polisyos.atlas.health_source_validator"),
        producer_version: z.literal("1.0.0"),
        python_executable: nonEmptyString,
        python_version: nonEmptyString,
        jsonschema_version: nonEmptyString,
        schema_dialect: z.literal(
          "https://json-schema.org/draft/2020-12/schema",
        ),
        implementation_ref: sourceRefSchema,
      })
      .strict(),
    readiness: z
      .object({
        as_of: nonEmptyString,
        entry_count: count,
        machine_audience_count: count,
        implemented_entry_count: count,
        source_refs: z.array(sourceRefSchema).min(2),
      })
      .strict(),
    audience: z
      .object({
        proxy_test_count: count,
        source_refs: z.array(sourceRefSchema).min(1),
      })
      .strict(),
    cluster: z
      .object({
        cell_count: z.number().int().positive(),
        implemented_cell_count: count,
        surface_missing_count: count,
        implemented_but_not_orchestrated_count: count,
        open_or_incomplete_count: count,
        open_cell_count: count,
        closure_contract_count: count,
        source_refs: z.array(sourceRefSchema).min(5),
      })
      .strict(),
    adoption: z
      .object({
        as_of: nonEmptyString,
        entry_count: count,
        stable_component_count: count,
        stable_with_browser_and_at_count: count,
        source_refs: z.array(sourceRefSchema).min(3),
      })
      .strict(),
  })
  .strict();

const HEALTH_CHILD_ENV = {
  HOME: "/var/empty",
  LANG: "C",
  LC_ALL: "C",
  PATH: "/usr/bin:/bin",
  TZ: "UTC",
} as const;

function policyEngineRoot(): string {
  const cwd = process.cwd();
  const candidates = [cwd, path.resolve(cwd, "../..")];
  const root = candidates.find((candidate) =>
    existsSync(path.join(candidate, HEALTH_SOURCE_VALIDATOR)),
  );
  if (!root) {
    throw new TypeError(
      "Atlas health metrics must run from policy-engine or apps/runtime-dashboard",
    );
  }
  return root;
}

function hashSource(
  root: string,
  relativePath: string,
  role: string,
): z.infer<typeof sourceRefSchema> {
  return {
    path: relativePath,
    sha256: createHash("sha256")
      .update(readFileSync(path.join(root, relativePath)))
      .digest("hex"),
    role,
  };
}

function gitOutput(root: string, args: readonly string[]): string {
  const result = spawnSync("/usr/bin/git", args, {
    cwd: root,
    encoding: "utf8",
    env: HEALTH_CHILD_ENV,
  });
  if (result.status !== 0) {
    throw new TypeError(
      `Atlas health git provenance failed (${String(result.status)}): ${result.stderr}`,
    );
  }
  return result.stdout;
}

function runHealthSourceValidator(root: string) {
  const repositoryPython = path.join(root, ".venv/bin/python");
  if (!existsSync(repositoryPython)) {
    throw new TypeError(
      "Atlas health measurement requires the repository-managed Python environment",
    );
  }
  const validatorPath = path.join(root, HEALTH_SOURCE_VALIDATOR);
  const result = spawnSync(repositoryPython, ["-I", validatorPath], {
    cwd: root,
    encoding: "utf8",
    env: HEALTH_CHILD_ENV,
    maxBuffer: 8 * 1024 * 1024,
  });
  if (result.status !== 0) {
    throw new TypeError(
      `Atlas health canonical-source validator failed (${String(result.status)}): ${result.stderr}`,
    );
  }
  return healthSourceProjectionSchema.parse(JSON.parse(result.stdout));
}

function directBasis(
  sourceRefs: z.infer<typeof sourceRefSchema>[],
  limitation: string | null,
  predicateProvenance: "recomputed" | "not_established" = "recomputed",
) {
  return observedBasisSchema.parse({
    kind: "observed_by_instrument",
    producer_id: HEALTH_PRODUCER_ID,
    producer_version: HEALTH_PRODUCER_VERSION,
    predicate_provenance: predicateProvenance,
    source_refs: sourceRefs,
    limitation,
  });
}

function observedRatio(numerator: number, denominator: number) {
  if (denominator <= 0) {
    throw new TypeError("observed ratios require a positive denominator");
  }
  if (numerator === 0) {
    return zeroMeasurementSchema.parse({
      kind: "zero",
      reason_code: "observed_zero",
      numerator: 0,
      denominator,
      ratio: 0,
      ranking: null,
    });
  }
  return measuredMeasurementSchema.parse({
    kind: "measured",
    reason_code: "observed_ratio",
    numerator,
    denominator,
    ratio: numerator / denominator,
    ranking: null,
  });
}

export function measureSurfaceMissingClosure(
  stateCounts: Readonly<Record<string, number>>,
  denominator: number,
) {
  const numerator =
    (stateCounts.surface_missing ?? 0) +
    (stateCounts.implemented_but_not_orchestrated ?? 0);
  return observedRatio(numerator, denominator);
}

export function measureAtlasHealthMetrics(): AtlasHealthMetricReport {
  const root = policyEngineRoot();
  const repositoryRevisionValue = gitOutput(root, ["rev-parse", "HEAD"]).trim();
  const repositoryDirty =
    gitOutput(root, ["status", "--porcelain=v1"]).trim() !== "";
  const sources = runHealthSourceValidator(root);
  const readinessEntryCount = sources.readiness.entry_count;
  const machineAudienceCount = sources.readiness.machine_audience_count;
  const implementedEntryCount = sources.readiness.implemented_entry_count;
  const stableComponentCount = sources.adoption.stable_component_count;
  const stableWithBrowserAndAt =
    sources.adoption.stable_with_browser_and_at_count;
  const honestyProfile = ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile;
  const commonReadinessRefs = sources.readiness.source_refs;

  return atlasHealthMetricReportSchema.parse({
    report_schema: ATLAS_HEALTH_METRIC_REPORT_SCHEMA,
    producer: {
      producer_id: HEALTH_PRODUCER_ID,
      producer_version: HEALTH_PRODUCER_VERSION,
      fixed_script: HEALTH_PRODUCER_SCRIPT,
      repository_revision: repositoryRevisionValue,
      repository_dirty: repositoryDirty,
      implementation_refs: [
        hashSource(root, HEALTH_PRODUCER_SOURCE, "typed_metric_producer"),
        hashSource(root, HEALTH_PRODUCER_SCRIPT, "fixed_process_launcher"),
        hashSource(root, HEALTH_SOURCE_VALIDATOR, "canonical_source_validator"),
      ],
    },
    measured_at: new Date().toISOString(),
    measurements: [
      {
        metric_id: "primitive_adoption",
        instrumentation_status: "instrumented",
        definition:
          "Share of decision-bearing renders flowing through DS4 primitives.",
        honest_direction: "Rising; 100% for authority slots.",
        scope: {
          scope_id: "ds1-live-readiness-rows",
          description: `All ${String(readinessEntryCount)} DS1 readiness rows at ${sources.readiness.as_of}.`,
        },
        basis: directBasis(
          commonReadinessRefs,
          "The owner has no exhaustive decision-bearing-render to DS4-primitive relation.",
          "not_established",
        ),
        measurement: {
          kind: "unknown",
          reason_code: "primitive_relation_not_established",
          predicate_provenance: "not_established",
        },
        known_facts: { readiness_entry_count: readinessEntryCount },
        thresholds: [],
      },
      {
        metric_id: "fail_closed_fidelity",
        instrumentation_status: "instrumented",
        definition:
          "Share of blocker, abstention, out-of-envelope, and stale-cached states rendered as typed states.",
        honest_direction: "Rising to 100%.",
        scope: {
          scope_id: "ds1-live-readiness-rows",
          description: `All ${String(readinessEntryCount)} DS1 readiness rows at ${sources.readiness.as_of}.`,
        },
        basis: directBasis(
          commonReadinessRefs,
          "The owner has no exhaustive semantic-state to rendered-state classifier.",
          "not_established",
        ),
        measurement: {
          kind: "unknown",
          reason_code: "render_state_denominator_not_established",
          predicate_provenance: "not_established",
        },
        known_facts: { readiness_entry_count: readinessEntryCount },
        thresholds: [],
      },
      {
        metric_id: "audience_enforcement",
        instrumentation_status: "instrumented",
        definition:
          "Share of audience-scoped endpoints with passing server-side deny tests.",
        honest_direction: "100% before DS12.",
        scope: {
          scope_id: "server-audience-denial-proxies",
          description:
            "The current source-level DS20 denial proxies; DS5 final audience mapping is absent.",
        },
        basis: directBasis(
          sources.audience.source_refs,
          "Six source proxies are neither a complete endpoint denominator nor a test-run receipt.",
          "not_established",
        ),
        measurement: {
          kind: "unknown",
          reason_code: "audience_endpoint_denominator_not_established",
          predicate_provenance: "not_established",
        },
        known_facts: { proxy_test_count: sources.audience.proxy_test_count },
        thresholds: [],
      },
      {
        metric_id: "surface_missing_closure",
        instrumentation_status: "instrumented",
        definition:
          "Open surface_missing or implemented_but_not_orchestrated links in the cluster map.",
        honest_direction: "Falling.",
        scope: {
          scope_id: "policy-design-case-cluster-map-cells",
          description: `All ${String(sources.cluster.cell_count)} canonical cluster-map cells.`,
        },
        basis: directBasis(
          sources.cluster.source_refs,
          "The canonical validator is a subordinate recomputation in this closed instrument, not an independent reconciliation.",
        ),
        measurement: measureSurfaceMissingClosure(
          {
            surface_missing: sources.cluster.surface_missing_count,
            implemented_but_not_orchestrated:
              sources.cluster.implemented_but_not_orchestrated_count,
          },
          sources.cluster.cell_count,
        ),
        known_facts: {
          cell_count: sources.cluster.cell_count,
          implemented_cell_count: sources.cluster.implemented_cell_count,
          surface_missing_count: sources.cluster.surface_missing_count,
          implemented_but_not_orchestrated_count:
            sources.cluster.implemented_but_not_orchestrated_count,
          open_or_incomplete_count: sources.cluster.open_or_incomplete_count,
          open_cell_count: sources.cluster.open_cell_count,
          closure_contract_count: sources.cluster.closure_contract_count,
        },
        thresholds: [],
      },
      {
        metric_id: "evidence_coverage",
        instrumentation_status: "instrumented",
        definition:
          "Share of stable components carrying browser and manual AT evidence.",
        honest_direction: "100% for stable.",
        scope: {
          scope_id: "ds2-adoption-ledger-stable-components",
          description: `All ${String(sources.adoption.entry_count)} DS2 adoption rows at ${sources.adoption.as_of}.`,
        },
        basis: directBasis(
          sources.adoption.source_refs,
          "No stable row exists, so the ratio and any ranking are undefined.",
        ),
        measurement:
          stableComponentCount === 0
            ? {
                kind: "incomparable",
                reason_code: "zero_denominator",
                numerator: stableWithBrowserAndAt,
                denominator: 0,
                ratio: null,
                ranking: null,
                scope_refs: [
                  "stable-components",
                  "browser-plus-at-manual-evidence",
                ],
              }
            : observedRatio(stableWithBrowserAndAt, stableComponentCount),
        known_facts: {
          adoption_entry_count: sources.adoption.entry_count,
          stable_component_count: stableComponentCount,
          stable_with_browser_and_at_count: stableWithBrowserAndAt,
        },
        thresholds: [],
      },
      {
        metric_id: "machine_twin_parity",
        instrumentation_status: "instrumented",
        definition:
          "Share of shipped surfaces with a passing machine-twin parity test.",
        honest_direction: "100%; twins ship in-slice.",
        scope: {
          scope_id: "ds1-live-readiness-rows",
          description: `All ${String(readinessEntryCount)} DS1 readiness rows at ${sources.readiness.as_of}.`,
        },
        basis: directBasis(
          commonReadinessRefs,
          "MACHINE audience and implemented state do not establish a shipped-surface/twin relation or parity receipt.",
          "not_established",
        ),
        measurement: {
          kind: "missing",
          reason_code: "machine_twin_relation_missing",
          expected_owner_ref: "atlas.surface-machine-twin-relation@not_present",
          ranking: null,
        },
        known_facts: {
          readiness_entry_count: readinessEntryCount,
          machine_audience_count: machineAudienceCount,
          implemented_entry_count: implementedEntryCount,
        },
        thresholds: [],
      },
      {
        metric_id: "honesty_comprehension",
        instrumentation_status: "protocol_seam_only",
        definition:
          "Reviewer-task success locating the weakest link and active blockers.",
        honest_direction: "Measured and reported; no benchmark exists yet.",
        scope: {
          scope_id: "ds6-honesty-comprehension-seed",
          description:
            "C12 seed tasks and the future INT-R3 behavioral battery.",
        },
        basis: directBasis(
          [
            hashSource(
              root,
              HONESTY_PROTOCOL_SOURCE,
              "c12_instrument_and_int_r3_seam",
            ),
          ],
          "INT-R3 content, observation artifact, and thresholds are not established.",
          "not_established",
        ),
        measurement: {
          kind: "missing",
          reason_code: "honesty_observation_missing",
          expected_owner_ref: "INT-R3/research-observation@not_established",
          ranking: null,
        },
        known_facts: {
          task_count: honestyProfile.tasks.length,
          metric_count: honestyProfile.metric_ids.length,
          research_input_status: honestyProfile.research_input.status,
          benchmark_status:
            ATLAS_HONESTY_COMPREHENSION_PROTOCOL.interpretation
              .benchmark_status,
        },
        thresholds: honestyProfile.thresholds,
      },
    ],
    interpretation: {
      posture: "candidate_only",
      aggregate_status: null,
      aggregate_ranking: null,
      grants_stable: false,
      blocking_permitted: false,
    },
    authority: {
      classification: "candidate_only",
      authoritative_for: [],
      may_not_use_for: [
        "descriptive_atlas_health_measurement",
        "component_maturity",
        "design_authority",
        "policy_authority",
        "promotion",
        "publication",
        "runtime_authority",
        "stable",
      ],
    },
  });
}

export function compareAtlasHealthMetricMeasurements(
  first: AtlasHealthMetricRow,
  second: AtlasHealthMetricRow,
) {
  if (first.metric_id !== second.metric_id) {
    return {
      status: "incomparable" as const,
      reason_code: "metric_identity_mismatch" as const,
      ranking: null,
    };
  }
  if (first.scope.scope_id !== second.scope.scope_id) {
    return {
      status: "incomparable" as const,
      reason_code: "scope_mismatch" as const,
      ranking: null,
    };
  }
  return {
    status: "incomparable" as const,
    reason_code: "ranking_not_defined" as const,
    ranking: null,
  };
}

const verificationSchema = z
  .object({
    ok: z.literal(true),
    artifact_id: artifactId,
    expected_sha256_hex: sha256,
    actual_sha256_hex: sha256,
    byte_size: z.number().int().positive(),
    error: z.null(),
  })
  .strict();

const artifactRefSchema = (kind: string) =>
  z
    .object({
      artifact_id: artifactId,
      kind: z.literal(kind),
      media_type: z.literal("application/json"),
    })
    .strict();

const admittedAuthoritySchema = z
  .object({
    classification: z.literal("limited_descriptive_admission"),
    authoritative_for: z.tuple([
      z.literal("descriptive_atlas_health_measurement"),
    ]),
    may_not_use_for: z.tuple([
      z.literal("component_maturity"),
      z.literal("design_authority"),
      z.literal("policy_authority"),
      z.literal("promotion"),
      z.literal("publication"),
      z.literal("runtime_authority"),
      z.literal("stable"),
    ]),
  })
  .strict();

const admittedInterpretationSchema = z
  .object({
    posture: z.literal("limited_descriptive_admission"),
    aggregate_status: z.null(),
    aggregate_ranking: z.null(),
    grants_stable: z.literal(false),
    blocking_permitted: z.literal(false),
  })
  .strict();

const replaySchema = z
  .object({
    status: z.enum(["revision_resolvable", "source_hash_bound_only"]),
    checked_path_count: z.number().int().positive(),
    non_revision_paths: z.array(nonEmptyString),
  })
  .strict()
  .superRefine((value, context) => {
    const hasNonRevisionPaths = value.non_revision_paths.length > 0;
    if (
      (value.status === "revision_resolvable" && hasNonRevisionPaths) ||
      (value.status === "source_hash_bound_only" && !hasNonRevisionPaths)
    ) {
      context.addIssue({
        code: "custom",
        message: "replay status must match the non-revision path set",
        path: ["status"],
      });
    }
    if (value.non_revision_paths.length > value.checked_path_count) {
      context.addIssue({
        code: "custom",
        message: "replay non-revision path count exceeds checked paths",
        path: ["non_revision_paths"],
      });
    }
  });

const snapshotSchema = z
  .object({
    snapshot_schema: z
      .object({
        id: z.literal(ATLAS_HEALTH_METRIC_SNAPSHOT_SCHEMA.id),
        version: z.literal(ATLAS_HEALTH_METRIC_SNAPSHOT_SCHEMA.version),
      })
      .strict(),
    report_ref: z
      .object({
        artifact_id: artifactId,
        kind: z.literal("atlas_health_metric_report"),
        media_type: z.literal("application/json"),
        schema_id: z.literal(ATLAS_HEALTH_METRIC_REPORT_SCHEMA.id),
        schema_version: z.literal(ATLAS_HEALTH_METRIC_REPORT_SCHEMA.version),
      })
      .strict(),
    report_sha256: sha256,
    measured_at: utcTimestamp,
    repository_revision: repositoryRevision,
    producer_observation: z
      .object({
        executable: nonEmptyString,
        allowed_locator: nonEmptyString,
        executable_sha256: sha256,
        executable_version: nonEmptyString,
        script: z.literal(HEALTH_PRODUCER_SCRIPT),
        script_sha256: sha256,
        process_exit_code: z.literal(0),
        stdout_sha256: sha256,
        environment: z
          .object({
            mode: z.literal("fixed_minimal_allowlist"),
            inherited_names: z.tuple([]),
            fixed: z
              .object({
                HOME: z.literal("/var/empty"),
                LANG: z.literal("C"),
                LC_ALL: z.literal("C"),
                PATH: z.literal("/usr/bin:/bin"),
                TZ: z.literal("UTC"),
              })
              .strict(),
            denied_prefixes: z.tuple([
              z.literal("NODE_"),
              z.literal("PYTHON"),
              z.literal("VITE_"),
              z.literal("npm_"),
              z.literal("NPM_"),
              z.literal("PNPM_"),
            ]),
          })
          .strict(),
      })
      .strict(),
    persistence_implementation: z
      .object({
        implementation_sha256: sha256,
        files: z.tuple([
          z
            .object({ path: z.literal(HEALTH_PRODUCER_SOURCE), sha256 })
            .strict(),
          z
            .object({ path: z.literal(HEALTH_PRODUCER_SCRIPT), sha256 })
            .strict(),
          z
            .object({ path: z.literal(HEALTH_SOURCE_VALIDATOR), sha256 })
            .strict(),
          z
            .object({
              path: z.literal(
                "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
              ),
              sha256,
            })
            .strict(),
          z.object({ path: z.literal("pyproject.toml"), sha256 }).strict(),
          z.object({ path: z.literal("uv.lock"), sha256 }).strict(),
        ]),
        repository_revision: repositoryRevision,
        dirty: z.boolean(),
      })
      .strict(),
    measurements: metricRowsSchema,
    admission: z
      .object({
        verifier_id: z.literal("polisyos.atlas.health_metric_admission"),
        verifier_version: z.literal("1.0.0"),
        predicate_provenance: z.literal("recomputed"),
        source_projection_sha256: sha256,
        source_validator: z
          .object({
            producer_id: z.literal("polisyos.atlas.health_source_validator"),
            producer_version: z.literal("1.0.0"),
            python_executable: nonEmptyString,
            python_version: nonEmptyString,
            jsonschema_version: nonEmptyString,
            schema_dialect: z.literal(
              "https://json-schema.org/draft/2020-12/schema",
            ),
            implementation_ref: z
              .object({
                path: z.literal(HEALTH_SOURCE_VALIDATOR),
                sha256,
                role: z.literal("canonical_source_validator"),
              })
              .strict(),
          })
          .strict(),
        source_validator_observation: z
          .object({
            executable: nonEmptyString,
            allowed_locator: nonEmptyString,
            executable_sha256: sha256,
            executable_version: nonEmptyString,
            validator: z.literal(HEALTH_SOURCE_VALIDATOR),
            validator_sha256: sha256,
            process_exit_code: z.literal(0),
            stdout_sha256: sha256,
            environment: z
              .object({
                mode: z.literal("fixed_minimal_allowlist"),
                inherited_names: z.tuple([]),
                fixed: z
                  .object({
                    HOME: z.literal("/var/empty"),
                    LANG: z.literal("C"),
                    LC_ALL: z.literal("C"),
                    PATH: z.literal("/usr/bin:/bin"),
                    TZ: z.literal("UTC"),
                  })
                  .strict(),
                isolated_python: z.literal(true),
              })
              .strict(),
          })
          .strict(),
        verifier_ref: sourceRefSchema,
      })
      .strict(),
    replay: replaySchema,
    authority: admittedAuthoritySchema,
    interpretation: admittedInterpretationSchema,
    capability: z
      .object({
        label: z.literal("implemented_but_not_orchestrated"),
        missing: z.tuple([
          z.literal("consumer_missing"),
          z.literal("surface_missing"),
        ]),
      })
      .strict(),
  })
  .strict();

const persistenceResultSchema = z
  .object({
    ok: z.literal(true),
    operation: z.literal(ATLAS_HEALTH_METRIC_PERSISTENCE_OPERATION),
    report_ref: artifactRefSchema("atlas_health_metric_report"),
    snapshot_ref: artifactRefSchema("atlas_health_metric_snapshot"),
    report_verification: verificationSchema,
    snapshot_verification: verificationSchema,
    report_manifest_input: z.null(),
    snapshot_manifest_input: z
      .object({
        artifact_id: artifactId,
        role: z.literal("measurement_report"),
      })
      .strict(),
    resolved_report: z
      .object({
        artifact_id: artifactId,
        report: atlasHealthMetricReportSchema,
      })
      .strict(),
    resolved_snapshot: z
      .object({
        artifact_id: artifactId,
        snapshot: snapshotSchema,
      })
      .strict(),
  })
  .strict();

export type AtlasHealthMetricPersistenceResult = z.infer<
  typeof persistenceResultSchema
>;

export function assertAtlasHealthMetricPersistenceResult(
  value: unknown,
): AtlasHealthMetricPersistenceResult {
  const result = persistenceResultSchema.parse(value);
  const reportId = result.report_ref.artifact_id;
  const snapshotId = result.snapshot_ref.artifact_id;
  const reportDigest = reportId.slice(7);
  if (
    result.report_verification.artifact_id !== reportId ||
    result.report_verification.expected_sha256_hex !== reportDigest ||
    result.report_verification.actual_sha256_hex !== reportDigest ||
    result.resolved_report.artifact_id !== reportId ||
    result.snapshot_manifest_input.artifact_id !== reportId ||
    result.resolved_snapshot.snapshot.report_ref.artifact_id !== reportId ||
    result.resolved_snapshot.snapshot.report_sha256 !== reportDigest ||
    result.resolved_snapshot.snapshot.producer_observation.stdout_sha256 !==
      reportDigest
  ) {
    throw new TypeError(
      "Atlas health report integrity or lineage binding mismatch",
    );
  }
  if (
    result.snapshot_verification.artifact_id !== snapshotId ||
    result.snapshot_verification.expected_sha256_hex !== snapshotId.slice(7) ||
    result.snapshot_verification.actual_sha256_hex !== snapshotId.slice(7) ||
    result.resolved_snapshot.artifact_id !== snapshotId
  ) {
    throw new TypeError("Atlas health snapshot integrity binding mismatch");
  }
  const report = result.resolved_report.report;
  const snapshot = result.resolved_snapshot.snapshot;
  if (
    snapshot.measured_at !== report.measured_at ||
    snapshot.repository_revision !== report.producer.repository_revision ||
    snapshot.persistence_implementation.repository_revision !==
      report.producer.repository_revision ||
    snapshot.admission.source_validator.python_executable !==
      snapshot.admission.source_validator_observation.executable ||
    snapshot.admission.source_validator.implementation_ref.sha256 !==
      snapshot.admission.source_validator_observation.validator_sha256 ||
    JSON.stringify(snapshot.measurements) !==
      JSON.stringify(report.measurements)
  ) {
    throw new TypeError("Atlas health snapshot semantic binding mismatch");
  }
  return result;
}
