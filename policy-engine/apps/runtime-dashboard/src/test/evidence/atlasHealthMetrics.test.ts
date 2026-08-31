import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmodSync,
  existsSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { beforeAll, describe, expect, it } from "vitest";

import { ATLAS_HONESTY_METRIC_IDS } from "./atlasHonestyComprehensionProtocol";
import {
  ATLAS_HEALTH_METRIC_IDS,
  ATLAS_HEALTH_METRIC_PERSISTENCE_OPERATION,
  atlasHealthMetricReportSchema,
  compareAtlasHealthMetricMeasurements,
  measureAtlasHealthMetrics,
  type AtlasHealthMetricReport,
} from "./atlasHealthMetrics";
import {
  DS18_MAX_STREAM_BYTES,
  decodeDs18ExecutionOutcome,
  primitiveAdoptionFromDs18Coverage,
  type Ds18ExecutionOutcome,
} from "./ds18ExecutionOutcome";

function clone<T>(value: T): T {
  return structuredClone(value);
}

function replaceMetric(
  report: AtlasHealthMetricReport,
  index: number,
  replacement: unknown,
): unknown {
  const candidate = clone(report) as unknown as { measurements: unknown[] };
  candidate.measurements[index] = replacement;
  return candidate;
}

function metric(
  report: AtlasHealthMetricReport,
  metricId: (typeof ATLAS_HEALTH_METRIC_IDS)[number],
) {
  const row = report.measurements.find(
    ({ metric_id }) => metric_id === metricId,
  );
  if (!row) {
    throw new TypeError(`missing fixture metric ${metricId}`);
  }
  return row;
}

function runDs18CanonicalChecker(): {
  status: number | null;
  stdout: Buffer;
  stderr: Buffer;
} {
  const dashboardRoot = process.cwd();
  const policyEngineRoot = path.resolve(dashboardRoot, "../..");
  const result = spawnSync(
    path.join(policyEngineRoot, ".venv/bin/python"),
    [
      "-I",
      path.join(
        policyEngineRoot,
        "architecture/atlas_surfaces/check_frontend_disposition_register.py",
      ),
      "--check-ds18-time-semantics-coverage",
    ],
    {
      cwd: policyEngineRoot,
      env: {
        HOME: "/var/empty",
        LANG: "C",
        LC_ALL: "C",
        PATH: "/usr/bin:/bin",
        POLISYOS_NODE_EXECUTABLE: process.execPath,
        TZ: "UTC",
      },
      maxBuffer: 2 * (8 * 1024 * 1024),
    },
  );
  return {
    status: result.status,
    stdout: result.stdout ?? Buffer.alloc(0),
    stderr: result.stderr ?? Buffer.alloc(0),
  };
}

function runDs18OutcomeRunner() {
  return spawnSync(
    process.execPath,
    ["scripts/run-ds18-time-semantics-outcome.mjs"],
    {
      cwd: process.cwd(),
      encoding: "utf8",
      maxBuffer: 2 * (8 * 1024 * 1024),
    },
  );
}

function invokePersistence(
  request: object,
  casRoot: string,
  environment: NodeJS.ProcessEnv = {},
): { status: number | null; value: unknown; stderr: string } {
  const dashboardRoot = process.cwd();
  const policyEngineRoot = path.resolve(dashboardRoot, "../..");
  const result = spawnSync(
    path.join(policyEngineRoot, ".venv/bin/python"),
    [path.join(dashboardRoot, "scripts/persist_atlas_evidence.py")],
    {
      cwd: policyEngineRoot,
      encoding: "utf8",
      input: JSON.stringify(request),
      env: {
        ...process.env,
        POLISYOS_CAS_BACKEND: "filesystem",
        POLISYOS_CAS_ROOT: casRoot,
        ...environment,
      },
      timeout: 60_000,
    },
  );
  return {
    status: result.status,
    value: JSON.parse(result.stdout) as unknown,
    stderr: result.stderr,
  };
}

describe("Atlas health metrics", () => {
  let report: AtlasHealthMetricReport;

  beforeAll(() => {
    report = measureAtlasHealthMetrics();
  }, 60_000);

  it("derives the exact seven-metric population and rejects a new identity", () => {
    expect(report.measurements.map(({ metric_id }) => metric_id)).toEqual(
      ATLAS_HEALTH_METRIC_IDS,
    );
    expect(report.measurements).toHaveLength(7);

    const added = clone(report) as unknown as {
      measurements: unknown[];
    };
    added.measurements.push({
      ...clone(report.measurements[0]),
      metric_id: "dashboard_green_rate",
    });
    expect(atlasHealthMetricReportSchema.safeParse(added).success).toBe(false);

    const removed = clone(report);
    removed.measurements.pop();
    expect(atlasHealthMetricReportSchema.safeParse(removed).success).toBe(
      false,
    );
    expect(
      report.producer.implementation_refs.map(({ path: filePath }) => filePath),
    ).toEqual([
      "apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts",
      "apps/runtime-dashboard/scripts/measure_atlas_health.mjs",
      "apps/runtime-dashboard/scripts/validate_atlas_health_sources.py",
    ]);
  });

  it("records the six current measurements and the seventh protocol seam honestly", () => {
    for (const row of report.measurements.slice(0, 6)) {
      expect(row.instrumentation_status).toBe("instrumented");
    }
    expect(metric(report, "fail_closed_fidelity").measurement.kind).toBe(
      "unknown",
    );
    expect(metric(report, "audience_enforcement").measurement.kind).toBe(
      "unknown",
    );
    expect(metric(report, "surface_missing_closure").measurement).toMatchObject(
      {
        kind: "zero",
        numerator: 0,
        denominator: 27,
        ratio: 0,
      },
    );
    expect(metric(report, "evidence_coverage").measurement).toMatchObject({
      kind: "incomparable",
      numerator: 0,
      denominator: 0,
      ratio: null,
      ranking: null,
    });
    expect(metric(report, "machine_twin_parity").measurement.kind).toBe(
      "missing",
    );

    const honesty = metric(report, "honesty_comprehension");
    expect(honesty.instrumentation_status).toBe("protocol_seam_only");
    expect(honesty.measurement.kind).toBe("missing");
    expect(honesty.thresholds).toEqual(
      ATLAS_HONESTY_METRIC_IDS.map((metric_id) => ({
        metric_id,
        status: "not_established",
        comparator: null,
        value: null,
        unit: null,
        source_ref: null,
      })),
    );
    expect(metric(report, "fail_closed_fidelity").known_facts).toMatchObject({
      readiness_entry_count: 261,
    });
    expect(metric(report, "surface_missing_closure").known_facts).toMatchObject(
      {
        cell_count: 27,
        open_or_incomplete_count: 0,
      },
    );
    expect(metric(report, "evidence_coverage").known_facts).toMatchObject({
      adoption_entry_count: 233,
      stable_component_count: 0,
      stable_with_browser_and_at_count: 0,
    });
  });

  it("derives primitive adoption from the live DS18 outcome instead of a local scalar", () => {
    const canonical = runDs18CanonicalChecker();
    const runner = runDs18OutcomeRunner();

    expect(runner).toMatchObject({ status: 0, stderr: "" });

    const outcome = JSON.parse(runner.stdout) as Ds18ExecutionOutcome;
    expect(outcome).toEqual(
      decodeDs18ExecutionOutcome({
        exitCode: canonical.status ?? 1,
        stdout: canonical.stdout,
        stderr: canonical.stderr,
      }),
    );
    const derived = primitiveAdoptionFromDs18Coverage(outcome);
    expect(metric(report, "primitive_adoption")).toMatchObject({
      scope: { description: derived.scope_description },
      basis: {
        predicate_provenance: derived.predicate_provenance,
        limitation: derived.limitation,
      },
      measurement: derived.measurement,
      known_facts: derived.known_facts,
    });
  }, 60_000);

  it("derives a synthetic 7/9 primitive-adoption measurement from an admitted outcome", () => {
    const outcome: Ds18ExecutionOutcome = {
      kind: "established",
      projection: {
        predicate_provenance: "independently_reconciled",
        source_file_count: 5,
        root_count: 12,
        obligated_root_count: 9,
        covered_root_count: 7,
      },
    };

    expect(primitiveAdoptionFromDs18Coverage(outcome)).toMatchObject({
      measurement: {
        kind: "measured",
        numerator: 7,
        denominator: 9,
        ratio: 7 / 9,
      },
      known_facts: {
        source_file_count: 5,
        render_root_count: 12,
        obligated_root_count: 9,
      },
    });
  });

  it("fails closed with bounded raw evidence for malformed DS18 checker output", () => {
    const invalidUtf8 = decodeDs18ExecutionOutcome({
      exitCode: 0,
      stdout: Buffer.from([0xff]),
      stderr: Buffer.alloc(0),
    });
    expect(invalidUtf8).toMatchObject({
      kind: "not_established",
      error_code: "stdout_invalid_utf8",
      exit_code: 0,
    });

    const malformedJson = decodeDs18ExecutionOutcome({
      exitCode: 0,
      stdout: Buffer.from("{", "utf8"),
      stderr: Buffer.alloc(0),
    });
    expect(malformedJson).toMatchObject({
      kind: "not_established",
      error_code: "stdout_invalid_json",
      exit_code: 0,
    });

    const invalidPacket = decodeDs18ExecutionOutcome({
      exitCode: 0,
      stdout: Buffer.from(
        JSON.stringify({
          predicate_provenance: "independently_reconciled",
          source_file_count: 5,
          root_count: 12,
          obligated_root_count: 9,
          covered_root_count: 7,
          extra: true,
        }),
        "utf8",
      ),
      stderr: Buffer.alloc(0),
    });
    expect(invalidPacket).toMatchObject({
      kind: "not_established",
      error_code: "stdout_invalid_packet",
      exit_code: 0,
    });

    const wrongPacket = decodeDs18ExecutionOutcome({
      exitCode: 0,
      stdout: Buffer.from(
        JSON.stringify({
          predicate_provenance: "recomputed",
          source_file_count: 5,
          root_count: 12,
          obligated_root_count: 9,
          covered_root_count: 7,
        }),
        "utf8",
      ),
      stderr: Buffer.alloc(0),
    });
    expect(wrongPacket).toMatchObject({
      kind: "not_established",
      error_code: "stdout_invalid_packet",
      exit_code: 0,
    });
  });

  it("bounds each raw checker stream independently", () => {
    const oversized = Buffer.alloc(DS18_MAX_STREAM_BYTES + 1);
    expect(
      decodeDs18ExecutionOutcome({
        exitCode: 0,
        stdout: oversized,
        stderr: Buffer.alloc(0),
      }),
    ).toMatchObject({
      error_code: "stdout_too_large",
      stdout_byte_count: DS18_MAX_STREAM_BYTES,
    });
    expect(
      decodeDs18ExecutionOutcome({
        exitCode: 0,
        stdout: Buffer.alloc(0),
        stderr: oversized,
      }),
    ).toMatchObject({
      error_code: "stderr_too_large",
      stderr_byte_count: DS18_MAX_STREAM_BYTES,
    });
  });

  it("preserves nonzero U+001C and U+FEFF stderr as raw fixed-code evidence", () => {
    for (const stderr of ["\u001c", "\ufeff"]) {
      const rawStderr = Buffer.from(stderr, "utf8");
      expect(
        decodeDs18ExecutionOutcome({
          exitCode: 1,
          stdout: Buffer.from("ignored", "utf8"),
          stderr: rawStderr,
        }),
      ).toEqual({
        kind: "not_established",
        error_code: "checker_exit_nonzero",
        exit_code: 1,
        stdout_byte_count: 7,
        stdout_sha256: `sha256:${createHash("sha256").update("ignored", "utf8").digest("hex")}`,
        stderr_byte_count: rawStderr.byteLength,
        stderr_sha256: `sha256:${createHash("sha256").update(rawStderr).digest("hex")}`,
      });
    }
  });

  it("drops primitive adoption to not established when its moving denominator is red", () => {
    const primitive = clone(metric(report, "primitive_adoption"));
    const candidate = replaceMetric(report, 0, {
      ...primitive,
      scope: {
        ...primitive.scope,
        description:
          "The post-freeze landing slice added an unreconciled decision-bearing root.",
      },
      basis: {
        ...primitive.basis,
        predicate_provenance: "not_established",
        limitation:
          "The landing-slice checker rejected an unreconciled render root.",
      },
      measurement: {
        kind: "unknown",
        reason_code: "time_semantics_coverage_not_established",
        predicate_provenance: "not_established",
      },
      known_facts: {
        source_file_count: 0,
        render_root_count: 0,
        obligated_root_count: 0,
      },
    });

    expect(atlasHealthMetricReportSchema.safeParse(candidate).success).toBe(
      true,
    );
  });

  it("keeps unknown, zero, missing, and incomparable structurally distinct", () => {
    const unknown = clone(metric(report, "fail_closed_fidelity"));
    expect(unknown.measurement.kind).toBe("unknown");
    (unknown.measurement as unknown as { value: number }).value = 0;
    const badUnknown = replaceMetric(report, 1, unknown);
    expect(atlasHealthMetricReportSchema.safeParse(badUnknown).success).toBe(
      false,
    );

    const zero = clone(metric(report, "surface_missing_closure"));
    (zero.measurement as { denominator: number }).denominator = 0;
    const badZero = replaceMetric(report, 3, zero);
    expect(atlasHealthMetricReportSchema.safeParse(badZero).success).toBe(
      false,
    );

    const missing = clone(metric(report, "machine_twin_parity"));
    (missing.measurement as unknown as { ratio: number }).ratio = 0;
    const badMissing = replaceMetric(report, 5, missing);
    expect(atlasHealthMetricReportSchema.safeParse(badMissing).success).toBe(
      false,
    );

    const incomparable = clone(metric(report, "evidence_coverage"));
    (incomparable.measurement as unknown as { ranking: string }).ranking =
      "higher";
    const badIncomparable = replaceMetric(report, 4, incomparable);
    expect(
      atlasHealthMetricReportSchema.safeParse(badIncomparable).success,
    ).toBe(false);
  });

  it("does not turn no observation into zero or an unavailable denominator into missing", () => {
    expect(metric(report, "honesty_comprehension").measurement.kind).toBe(
      "missing",
    );
    for (const metricId of [
      "fail_closed_fidelity",
      "audience_enforcement",
    ] as const) {
      expect(metric(report, metricId).measurement.kind).toBe("unknown");
    }
  });

  it("produces no ranking for incomparable scopes", () => {
    const first = clone(metric(report, "evidence_coverage"));
    const second = clone(first);
    (
      second as unknown as { scope: { scope_id: string; description: string } }
    ).scope = {
      scope_id: "atlas-components-at-another-cutoff",
      description: "A different component and cutoff scope.",
    };
    expect(compareAtlasHealthMetricMeasurements(first, second)).toEqual({
      status: "incomparable",
      reason_code: "scope_mismatch",
      ranking: null,
    });
  });

  it("keeps every metric on the closed instrument without claiming independence", () => {
    for (const metricId of ATLAS_HEALTH_METRIC_IDS) {
      const row = metric(report, metricId);
      expect(row.basis.kind).toBe("observed_by_instrument");
    }
    for (const metricId of [
      "fail_closed_fidelity",
      "audience_enforcement",
      "machine_twin_parity",
      "honesty_comprehension",
    ] as const) {
      expect(metric(report, metricId).basis.predicate_provenance).toBe(
        "not_established",
      );
    }
    expect(metric(report, "surface_missing_closure").basis).toMatchObject({
      kind: "observed_by_instrument",
      predicate_provenance: "recomputed",
    });
    expect(metric(report, "evidence_coverage").basis).toMatchObject({
      kind: "observed_by_instrument",
      predicate_provenance: "recomputed",
    });
    expect(metric(report, "primitive_adoption").basis).toMatchObject({
      kind: "observed_by_instrument",
      predicate_provenance:
        metric(report, "primitive_adoption").measurement.kind === "unknown"
          ? "not_established"
          : "recomputed",
    });
    expect(
      metric(report, "surface_missing_closure").measurement.reason_code,
    ).toBe("observed_zero");
    expect(report).not.toHaveProperty("pass");
    expect(report.interpretation).toMatchObject({
      posture: "candidate_only",
      aggregate_status: null,
      aggregate_ranking: null,
      grants_stable: false,
      blocking_permitted: false,
    });
  });

  it("binds every metric identity to its exact status, basis, state, and facts", () => {
    const mutated = [
      replaceMetric(report, 0, {
        ...clone(metric(report, "primitive_adoption")),
        instrumentation_status: "protocol_seam_only",
      }),
      replaceMetric(report, 1, {
        ...clone(metric(report, "fail_closed_fidelity")),
        basis: clone(metric(report, "surface_missing_closure").basis),
      }),
      replaceMetric(report, 2, {
        ...clone(metric(report, "audience_enforcement")),
        measurement: clone(
          metric(report, "surface_missing_closure").measurement,
        ),
      }),
      replaceMetric(report, 3, {
        ...clone(metric(report, "surface_missing_closure")),
        known_facts: { cell_count: 27 },
      }),
      replaceMetric(report, 3, {
        ...clone(metric(report, "surface_missing_closure")),
        known_facts: {
          ...clone(metric(report, "surface_missing_closure").known_facts),
          cell_count: 28,
        },
      }),
      replaceMetric(report, 3, {
        ...clone(metric(report, "surface_missing_closure")),
        basis: {
          kind: "consistent_with_cited_report",
          producer_id: "forged.validator",
          producer_version: "1.0.0",
          predicate_provenance: "recomputed",
          source_refs: clone(
            metric(report, "surface_missing_closure").basis.source_refs,
          ),
          limitation: null,
        },
      }),
      replaceMetric(report, 5, {
        ...clone(metric(report, "machine_twin_parity")),
        basis: {
          ...clone(metric(report, "machine_twin_parity").basis),
          predicate_provenance: "recomputed",
        },
      }),
    ];
    for (const candidate of mutated) {
      expect(atlasHealthMetricReportSchema.safeParse(candidate).success).toBe(
        false,
      );
    }
  });

  it("rejects measured or zero authority whenever the predicate is not established", () => {
    const observedZero = clone(
      metric(report, "surface_missing_closure").measurement,
    );
    for (const [index, metricId] of [
      [1, "fail_closed_fidelity"],
      [2, "audience_enforcement"],
      [5, "machine_twin_parity"],
      [6, "honesty_comprehension"],
    ] as const) {
      const candidate = replaceMetric(report, index, {
        ...clone(metric(report, metricId)),
        measurement: observedZero,
      });
      expect(atlasHealthMetricReportSchema.safeParse(candidate).success).toBe(
        false,
      );
    }
  });

  it("binds surface closure to its two target states, not every open state", () => {
    const mixed = clone(
      metric(report, "surface_missing_closure"),
    ) as unknown as {
      known_facts: Record<string, number>;
      measurement: Record<string, unknown>;
    };
    mixed.known_facts = {
      ...mixed.known_facts,
      implemented_cell_count: 23,
      surface_missing_count: 1,
      implemented_but_not_orchestrated_count: 2,
      open_or_incomplete_count: 4,
      open_cell_count: 4,
      closure_contract_count: 4,
    };
    mixed.measurement = {
      kind: "measured",
      reason_code: "observed_ratio",
      numerator: 3,
      denominator: 27,
      ratio: 3 / 27,
      ranking: null,
    };
    expect(
      atlasHealthMetricReportSchema.safeParse(replaceMetric(report, 3, mixed))
        .success,
    ).toBe(true);

    const conflated = clone(mixed);
    conflated.measurement = {
      ...conflated.measurement,
      numerator: 4,
      ratio: 4 / 27,
    };
    expect(
      atlasHealthMetricReportSchema.safeParse(
        replaceMetric(report, 3, conflated),
      ).success,
    ).toBe(false);
  });

  it("runs full canonical owner-schema corruption probes without editing owners", () => {
    const dashboardRoot = process.cwd();
    const policyEngineRoot = path.resolve(dashboardRoot, "../..");
    const result = spawnSync(
      path.join(policyEngineRoot, ".venv/bin/python"),
      [
        path.join(dashboardRoot, "scripts/validate_atlas_health_sources.py"),
        "--corruption-probes",
      ],
      {
        cwd: policyEngineRoot,
        encoding: "utf8",
        env: {
          HOME: "/var/empty",
          LANG: "C",
          LC_ALL: "C",
          PATH: "/usr/bin:/bin",
          TZ: "UTC",
        },
      },
    );
    expect(result).toMatchObject({ status: 0, stderr: "" });
    expect(JSON.parse(result.stdout)).toEqual({
      ok: true,
      probes: [
        "readiness_required",
        "readiness_additional_property",
        "readiness_unique_audience",
        "readiness_datetime_format",
        "readiness_duplicate_surface_id",
        "adoption_enum",
        "adoption_date_format",
        "adoption_stable_evidence",
        "adoption_duplicate_id",
      ],
    });
  });

  it("rejects duplicate canonical owner identities even when each row is schema-valid", () => {
    const dashboardRoot = process.cwd();
    const policyEngineRoot = path.resolve(dashboardRoot, "../..");
    const validatorPath = path.join(
      dashboardRoot,
      "scripts/validate_atlas_health_sources.py",
    );
    const program = [
      "import copy, importlib.util, json",
      `spec = importlib.util.spec_from_file_location("atlas_health_sources", ${JSON.stringify(validatorPath)})`,
      "module = importlib.util.module_from_spec(spec)",
      "spec.loader.exec_module(module)",
      "results = {}",
      "for owner, owner_path, key in [('readiness', module.READINESS_PATH, 'surface_id'), ('adoption', module.ADOPTION_PATH, 'id')]:",
      "    value = json.loads((module.REPO_ROOT / owner_path).read_text(encoding='utf-8'))",
      "    value['entries'].append(copy.deepcopy(value['entries'][0]))",
      "    try:",
      "        module.validate_owner_instance(owner, value)",
      "    except module.AtlasHealthSourceError:",
      "        results[f'{owner}_duplicate_{key}'] = 'rejected'",
      "    else:",
      "        results[f'{owner}_duplicate_{key}'] = 'accepted'",
      "print(json.dumps(results, sort_keys=True))",
    ].join("\n");
    const result = spawnSync(
      path.join(policyEngineRoot, ".venv/bin/python"),
      ["-I", "-c", program],
      {
        cwd: policyEngineRoot,
        encoding: "utf8",
        env: {
          HOME: "/var/empty",
          LANG: "C",
          LC_ALL: "C",
          PATH: "/usr/bin:/bin",
          TZ: "UTC",
        },
      },
    );
    expect(result).toMatchObject({ status: 0, stderr: "" });
    expect(JSON.parse(result.stdout)).toEqual({
      adoption_duplicate_id: "rejected",
      readiness_duplicate_surface_id: "rejected",
    });
  });

  it("replay comparator degrades a content binding absent from the recorded revision", () => {
    const dashboardRoot = process.cwd();
    const policyEngineRoot = path.resolve(dashboardRoot, "../..");
    const adapterPath = path.join(
      dashboardRoot,
      "scripts/persist_atlas_evidence.py",
    );
    const program = [
      "import importlib.util, json",
      `spec = importlib.util.spec_from_file_location("atlas_persistence", ${JSON.stringify(adapterPath)})`,
      "module = importlib.util.module_from_spec(spec)",
      "spec.loader.exec_module(module)",
      "report = {'measurements': [{'basis': {'source_refs': [{'path': 'apps/runtime-dashboard/not-in-revision.ts'}]}}]}",
      "print(json.dumps(module._health_replay_status(module._run_git('rev-parse', 'HEAD').strip(), report)))",
    ].join("\n");
    const result = spawnSync(
      path.join(policyEngineRoot, ".venv/bin/python"),
      ["-c", program],
      {
        cwd: policyEngineRoot,
        encoding: "utf8",
        env: {
          HOME: "/var/empty",
          LANG: "C",
          LC_ALL: "C",
          PATH: "/usr/bin:/bin",
          TZ: "UTC",
        },
      },
    );
    expect(result).toMatchObject({ status: 0, stderr: "" });
    const replay = JSON.parse(result.stdout) as {
      status: string;
      non_revision_paths: string[];
    };
    expect(replay.status).toBe("source_hash_bound_only");
    expect(replay.non_revision_paths).toContain(
      "apps/runtime-dashboard/not-in-revision.ts",
    );
  });

  it("replays a clean product-relative bound path and degrades an absent path", () => {
    const dashboardRoot = process.cwd();
    const policyEngineRoot = path.resolve(dashboardRoot, "../..");
    const adapterPath = path.join(
      dashboardRoot,
      "scripts/persist_atlas_evidence.py",
    );
    const program = [
      "import importlib.util, json",
      `spec = importlib.util.spec_from_file_location("atlas_persistence", ${JSON.stringify(adapterPath)})`,
      "module = importlib.util.module_from_spec(spec)",
      "spec.loader.exec_module(module)",
      "revision = module._run_git('rev-parse', 'HEAD').strip()",
      "print(json.dumps({'clean': module._revision_byte_status(revision, {'CONTRIBUTING.md'}), 'absent': module._revision_byte_status(revision, {'apps/runtime-dashboard/not-in-revision.ts'})}, sort_keys=True))",
    ].join("\n");
    const result = spawnSync(
      path.join(policyEngineRoot, ".venv/bin/python"),
      ["-c", program],
      {
        cwd: policyEngineRoot,
        encoding: "utf8",
        env: {
          HOME: "/var/empty",
          LANG: "C",
          LC_ALL: "C",
          PATH: "/usr/bin:/bin",
          TZ: "UTC",
        },
      },
    );
    expect(result).toMatchObject({ status: 0, stderr: "" });
    expect(JSON.parse(result.stdout)).toEqual({
      absent: {
        checked_path_count: 1,
        non_revision_paths: ["apps/runtime-dashboard/not-in-revision.ts"],
        status: "source_hash_bound_only",
      },
      clean: {
        checked_path_count: 1,
        non_revision_paths: [],
        status: "revision_resolvable",
      },
    });
  });

  it("refuses MACHINE audience and source-level proxy tests as metric passes", () => {
    const machine = metric(report, "machine_twin_parity");
    expect(machine.known_facts).toMatchObject({
      readiness_entry_count: 261,
      machine_audience_count: 193,
      implemented_entry_count: 5,
    });
    expect(machine.measurement.kind).toBe("missing");

    const audience = metric(report, "audience_enforcement");
    expect(audience.known_facts).toMatchObject({ proxy_test_count: 7 });
    expect(audience.measurement.kind).toBe("unknown");
    expect(audience.known_facts).not.toHaveProperty("passed_test_count");
  });

  it("registers the unchanged Python persistence adapter as consumer missing", () => {
    const casRoot = mkdtempSync(path.join(tmpdir(), "atlas-health-cas-"));
    try {
      const result = invokePersistence(
        { operation: ATLAS_HEALTH_METRIC_PERSISTENCE_OPERATION },
        casRoot,
      );
      expect(result).toMatchObject({ status: 1, stderr: "" });
      expect(result.value).toEqual({
        ok: false,
        operation: ATLAS_HEALTH_METRIC_PERSISTENCE_OPERATION,
        error: {
          code: "atlas_evidence_persistence_failed",
          message:
            "health-metric rows do not bind the recomputed canonical-source projection",
          type: "AtlasEvidencePersistenceError",
        },
      });
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
    }
  });

  it("ignores a caller PATH node that emits a schema-valid forged report", () => {
    const casRoot = mkdtempSync(path.join(tmpdir(), "atlas-health-path-cas-"));
    const fakeRoot = mkdtempSync(
      path.join(tmpdir(), "atlas-health-fake-node-"),
    );
    try {
      const marker = path.join(fakeRoot, "fake-node-ran");
      const forgedReport = clone(report) as unknown as {
        measurements: Array<Record<string, unknown>>;
      };
      forgedReport.measurements[0].measurement = clone(
        metric(report, "surface_missing_closure").measurement,
      );
      const reportPath = path.join(fakeRoot, "forged-report.json");
      writeFileSync(reportPath, JSON.stringify(forgedReport), "utf8");
      const fakeNode = path.join(fakeRoot, "node");
      writeFileSync(
        fakeNode,
        [
          "#!/usr/bin/python3",
          "from pathlib import Path",
          `Path(${JSON.stringify(marker)}).write_text("invoked")`,
          `print(Path(${JSON.stringify(reportPath)}).read_text())`,
          "",
        ].join("\n"),
        "utf8",
      );
      chmodSync(fakeNode, 0o755);

      const result = invokePersistence(
        { operation: ATLAS_HEALTH_METRIC_PERSISTENCE_OPERATION },
        casRoot,
        { PATH: fakeRoot },
      );
      expect(result).toMatchObject({ status: 1, stderr: "" });
      expect(result.value).toMatchObject({
        error: { code: "atlas_evidence_persistence_failed" },
      });
      expect(existsSync(marker)).toBe(false);
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
      rmSync(fakeRoot, { recursive: true, force: true });
    }
  });

  it("does not inherit caller NODE_OPTIONS into the fixed producer", () => {
    const casRoot = mkdtempSync(
      path.join(tmpdir(), "atlas-health-node-options-cas-"),
    );
    const injectionRoot = mkdtempSync(
      path.join(tmpdir(), "atlas-health-node-options-"),
    );
    try {
      const marker = path.join(injectionRoot, "node-options-loaded");
      const preload = path.join(injectionRoot, "preload.cjs");
      writeFileSync(
        preload,
        `require("node:fs").writeFileSync(${JSON.stringify(marker)}, "loaded");\n`,
        "utf8",
      );
      const result = invokePersistence(
        { operation: ATLAS_HEALTH_METRIC_PERSISTENCE_OPERATION },
        casRoot,
        { NODE_OPTIONS: `--require=${preload}` },
      );
      expect(result).toMatchObject({ status: 1, stderr: "" });
      expect(result.value).toMatchObject({
        error: { code: "atlas_evidence_persistence_failed" },
      });
      expect(existsSync(marker)).toBe(false);
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
      rmSync(injectionRoot, { recursive: true, force: true });
    }
  });

  it.each([
    "report",
    "repository_root",
    "producer_script",
    "exit_code",
    "basis",
  ])("rejects caller-supplied C11 intake field %s", (field) => {
    const casRoot = mkdtempSync(path.join(tmpdir(), "atlas-health-reject-"));
    try {
      const result = invokePersistence(
        {
          operation: ATLAS_HEALTH_METRIC_PERSISTENCE_OPERATION,
          [field]: field === "exit_code" ? 0 : "supplied",
        },
        casRoot,
      );
      expect(result.status).toBe(1);
      expect(result.value).toMatchObject({
        ok: false,
        operation: ATLAS_HEALTH_METRIC_PERSISTENCE_OPERATION,
        error: { code: "atlas_evidence_persistence_failed" },
      });
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
    }
  });
});
