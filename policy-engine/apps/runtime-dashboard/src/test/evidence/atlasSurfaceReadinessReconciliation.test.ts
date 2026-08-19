import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterAll, describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/app/routes/routes";

import {
  assertValidatedReadinessOwnerBytes,
  AtlasSurfaceReadinessContractError,
  type AtlasSurfaceReadinessClaim,
  buildAtlasStableReadinessNegativeControl,
  buildConsistentWithCitedReportClaim,
  inspectAtlasRuntimeRedirect,
  parseAtlasSurfaceReadinessClaim,
} from "./atlasSurfaceReadinessReconciliation";

const OPERATION = "persist_atlas_surface_readiness_claims";
const OBSERVED_ATTESTATION_SCOPE =
  "observed_by_reconciler attests intake closure: this process produced the row through a closed path by running each available applicable canonical check itself and recording any unavailable claim check as unavailable; no report, exit code, status, or basis was supplied by a caller, and runner code being unmodified on disk is not attested.";

interface PersistenceResult {
  status: number | null;
  stderr: string;
  value: Record<string, unknown>;
}

interface ProjectionResult {
  operation: string;
  claim_report_ref: { artifact_id: string };
  projection_ref: { artifact_id: string };
  claim_report_manifest_input: null;
  projection_manifest_input: { artifact_id: string; role: string };
  resolved_claim_report: {
    artifact_id: string;
    report: {
      report_schema: { id: string; version: string };
      claims: AtlasSurfaceReadinessClaim[];
      producer: {
        vite_loader: { path: string; sha256: string; version: string };
      };
    };
  };
  resolved_projection: {
    artifact_id: string;
    projection: {
      projection_schema: { id: string; version: string };
      claim_report_ref: { artifact_id: string };
      claim_report_sha256: string;
      claims: AtlasSurfaceReadinessClaim[];
    };
  };
}

function invokePersistence(
  request: object,
  casRoot: string,
  extraEnv: NodeJS.ProcessEnv = {},
): PersistenceResult {
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
        ...extraEnv,
        POLISYOS_CAS_BACKEND: "filesystem",
        POLISYOS_CAS_ROOT: casRoot,
      },
      timeout: 60_000,
    },
  );
  return {
    status: result.status,
    stderr: result.stderr,
    value: JSON.parse(result.stdout) as Record<string, unknown>,
  };
}

function asProjectionResult(result: PersistenceResult): ProjectionResult {
  if (result.status !== 0 || result.stderr !== "") {
    throw new Error(
      `closed persistence failed (${String(result.status)}): ${result.stderr}`,
    );
  }
  return result.value as unknown as ProjectionResult;
}

function observedClaim(result: ProjectionResult): AtlasSurfaceReadinessClaim {
  const claim = result.resolved_projection.projection.claims[0];
  expect(claim?.basis.kind).toBe("observed_by_reconciler");
  if (claim === undefined) {
    throw new Error("current projection has no claim control row");
  }
  return claim;
}

function citedBasis(claim: AtlasSurfaceReadinessClaim) {
  if (claim.basis.kind !== "consistent_with_cited_report") {
    throw new Error("claim does not carry a cited-report basis");
  }
  return claim.basis;
}

function citedReportBytes(
  executionStatus: "pass" | "fail" | "incomplete",
  findings: Array<{ code: string; message: string }>,
): Buffer {
  return Buffer.from(
    JSON.stringify({
      report_schema: {
        id: "polisyos.atlas.cited-surface-readiness-report",
        version: "1.0.0",
      },
      producer: {
        producer_id: "institution.route-test-producer",
        producer_version: "1.0.0",
      },
      execution_status: executionStatus,
      findings,
    }),
  );
}

function observedVariant(
  claim: AtlasSurfaceReadinessClaim,
  status: "not_observed" | "observation_unavailable",
): unknown {
  if (claim.basis.kind !== "observed_by_reconciler") {
    throw new Error("control claim must have an observed basis");
  }
  const unavailable = status === "observation_unavailable";
  return {
    ...claim,
    predicate_provenance: unavailable ? "not_established" : "recomputed",
    basis: {
      ...claim.basis,
      observation: {
        status,
        reason: unavailable
          ? "canonical_route_harness_failed"
          : "canonical_assertion_failed",
      },
      canonical_check: {
        ...claim.basis.canonical_check,
        report_sha256: unavailable
          ? null
          : claim.basis.canonical_check.report_sha256,
        assertion_status: unavailable ? null : "failed",
      },
    },
  };
}

function gateCode(value: unknown, citedReport?: Uint8Array): string | null {
  try {
    assertClaimObservationForCi(value, citedReport);
    return null;
  } catch (error) {
    expect(error).toBeInstanceOf(AtlasSurfaceReadinessContractError);
    return (error as AtlasSurfaceReadinessContractError).code;
  }
}

function assertClaimObservationForCi(
  value: unknown,
  citedReport?: Uint8Array,
): void {
  const claim = parseAtlasSurfaceReadinessClaim(value, citedReport);
  if (claim.basis.kind === "consistent_with_cited_report") {
    throw new AtlasSurfaceReadinessContractError(
      "cited_report_not_observation",
      `${claim.claim_id} cites a consistent report but is not observed`,
    );
  }
  if (claim.basis.observation.status === "observation_unavailable") {
    throw new AtlasSurfaceReadinessContractError(
      "claim_observation_unavailable",
      `${claim.claim_id} could not be observed: ${claim.basis.observation.reason}`,
    );
  }
  if (claim.basis.observation.status === "not_observed") {
    throw new AtlasSurfaceReadinessContractError(
      "canonical_claim_not_observed",
      `${claim.claim_id} was canonically observed not to hold`,
    );
  }
}

describe("Atlas surface-readiness per-claim reconciliation", () => {
  const casRoot = mkdtempSync(path.join(tmpdir(), "atlas-readiness-cas-"));

  afterAll(() => {
    rmSync(casRoot, { recursive: true, force: true });
  });

  const persisted = asProjectionResult(
    invokePersistence({ operation: OPERATION }, casRoot),
  );
  const independentlyDiscoveredGates =
    persisted.resolved_projection.projection.claims.map(
      (claim) =>
        [
          claim.claim_id,
          claim,
          () => assertClaimObservationForCi(claim),
        ] as const,
    );

  it("enumerates the complete gated owner set through the admitted projection", () => {
    expect(persisted.operation).toBe(OPERATION);
    expect(independentlyDiscoveredGates).toHaveLength(5);
  });

  it.each(persisted.resolved_projection.projection.claims)(
    "persists the exact intake-closure threat model on $claim_id",
    (claim) => {
      expect(claim).toMatchObject({
        basis: {
          kind: "observed_by_reconciler",
          attestation_scope: OBSERVED_ATTESTATION_SCOPE,
        },
      });
    },
  );

  it("versions the required threat-model field in both persisted schemas", () => {
    expect(persisted.resolved_claim_report.report.report_schema.version).toBe(
      "2.0.0",
    );
    expect(
      persisted.resolved_projection.projection.projection_schema.version,
    ).toBe("2.0.0");
  });

  it.each(independentlyDiscoveredGates)(
    "CI independently gates %s without changing artifact bytes",
    (_claimId, claim, admittedGate) => {
      const artifactsWithoutGate = JSON.stringify({
        report: persisted.resolved_claim_report.report,
        projection: persisted.resolved_projection.projection,
      });

      expect(admittedGate).not.toThrow();
      expect(claim).toMatchObject({
        predicate_provenance: "recomputed",
        basis: {
          kind: "observed_by_reconciler",
          observation: { status: "observed", reason: null },
        },
      });

      expect(
        JSON.stringify({
          report: persisted.resolved_claim_report.report,
          projection: persisted.resolved_projection.projection,
        }),
      ).toBe(artifactsWithoutGate);
    },
  );

  it("binds the claim report into the governed Core CAS audit projection", () => {
    expect(persisted.claim_report_manifest_input).toBeNull();
    expect(persisted.projection_manifest_input).toEqual({
      artifact_id: persisted.claim_report_ref.artifact_id,
      role: "claim_report",
    });
    expect(
      persisted.resolved_projection.projection.claim_report_ref.artifact_id,
    ).toBe(persisted.claim_report_ref.artifact_id);
    expect(persisted.resolved_claim_report.artifact_id).toBe(
      persisted.claim_report_ref.artifact_id,
    );
    expect(persisted.resolved_projection.artifact_id).toBe(
      persisted.projection_ref.artifact_id,
    );
    expect(persisted.resolved_claim_report.report.claims).toEqual(
      persisted.resolved_projection.projection.claims,
    );
  });

  it("allows only the per-row report, projection, and adapter fields", () => {
    expect(Object.keys(persisted).sort()).toEqual([
      "claim_report_manifest_input",
      "claim_report_ref",
      "operation",
      "projection_manifest_input",
      "projection_ref",
      "resolved_claim_report",
      "resolved_projection",
    ]);
    expect(Object.keys(persisted.resolved_claim_report.report).sort()).toEqual([
      "claims",
      "producer",
      "report_schema",
    ]);
    expect(
      Object.keys(persisted.resolved_claim_report.report.producer).sort(),
    ).toEqual([
      "implementation_ref",
      "producer_id",
      "producer_version",
      "vite_loader",
    ]);
    expect(
      Object.keys(persisted.resolved_projection.projection).sort(),
    ).toEqual([
      "authority",
      "claim_report_ref",
      "claim_report_sha256",
      "claims",
      "projection_schema",
      "verifier",
    ]);
  });

  it("keeps a legitimate cited report reportable but ineligible as observation", () => {
    const bytes = citedReportBytes("pass", []);
    const cited = buildConsistentWithCitedReportClaim(
      observedClaim(persisted),
      bytes,
    );

    expect(cited.basis.kind).toBe("consistent_with_cited_report");
    const digest = createHash("sha256").update(bytes).digest("hex");
    expect(citedBasis(cited).artifact).toMatchObject({
      artifact_id: `sha256:${digest}`,
      sha256: digest,
    });
    expect(() => parseAtlasSurfaceReadinessClaim(cited)).toThrow(
      expect.objectContaining({ code: "cited_report_bytes_required" }),
    );
    expect(parseAtlasSurfaceReadinessClaim(cited, bytes)).toEqual(cited);
    expect(() =>
      parseAtlasSurfaceReadinessClaim(
        cited,
        citedReportBytes("fail", [
          { code: "route_missing", message: "The canonical route was absent." },
        ]),
      ),
    ).toThrow(
      expect.objectContaining({ code: "cited_report_content_mismatch" }),
    );
    expect(gateCode(cited, bytes)).toBe("cited_report_not_observation");
  });

  it("rejects cited pass with canonical findings under its named mismatch", () => {
    expect(() =>
      buildConsistentWithCitedReportClaim(
        observedClaim(persisted),
        citedReportBytes("pass", [
          { code: "route_missing", message: "The canonical route was absent." },
        ]),
      ),
    ).toThrow(expect.objectContaining({ code: "cited_pass_with_findings" }));
  });

  it.each(["fail", "incomplete"] as const)(
    "rejects cited %s with zero findings under the opposite named mismatch",
    (executionStatus) => {
      expect(() =>
        buildConsistentWithCitedReportClaim(
          observedClaim(persisted),
          citedReportBytes(executionStatus, []),
        ),
      ).toThrow(
        expect.objectContaining({ code: "cited_nonpass_without_findings" }),
      );
    },
  );

  it("distinguishes a completed negative from an unavailable observation", () => {
    const claim = observedClaim(persisted);
    const negative = parseAtlasSurfaceReadinessClaim(
      observedVariant(claim, "not_observed"),
    );
    const unavailable = parseAtlasSurfaceReadinessClaim(
      observedVariant(claim, "observation_unavailable"),
    );

    expect(gateCode(negative)).toBe("canonical_claim_not_observed");
    expect(gateCode(unavailable)).toBe("claim_observation_unavailable");
  });

  it("rejects unavailable beside a completed assertion and completed without a report", () => {
    const claim = observedClaim(persisted);
    if (claim.basis.kind !== "observed_by_reconciler") {
      throw new Error("control claim must have an observed basis");
    }
    const unavailableWithPass = {
      ...(observedVariant(claim, "observation_unavailable") as Record<
        string,
        unknown
      >),
      basis: {
        ...claim.basis,
        observation: {
          status: "observation_unavailable",
          reason: "canonical_route_harness_failed",
        },
        canonical_check: {
          ...claim.basis.canonical_check,
          assertion_status: "passed",
        },
      },
      predicate_provenance: "not_established",
    };
    const observedWithoutReport = {
      ...claim,
      basis: {
        ...claim.basis,
        canonical_check: {
          ...claim.basis.canonical_check,
          report_sha256: null,
        },
      },
    };

    expect(() => parseAtlasSurfaceReadinessClaim(unavailableWithPass)).toThrow(
      expect.objectContaining({ code: "unavailable_with_completed_assertion" }),
    );
    expect(() =>
      parseAtlasSurfaceReadinessClaim(observedWithoutReport),
    ).toThrow(
      expect.objectContaining({ code: "completed_observation_without_report" }),
    );
  });

  it("binds the resolved Vitest entry, version, and bytes on every live row", () => {
    const claim = observedClaim(persisted);
    if (claim.basis.kind !== "observed_by_reconciler") {
      throw new Error("control claim must have an observed basis");
    }
    const entryPath = realpathSync(
      path.join(process.cwd(), "node_modules/vitest/vitest.mjs"),
    );
    const packageValue = JSON.parse(
      readFileSync(path.join(path.dirname(entryPath), "package.json"), "utf8"),
    ) as { version: string };
    expect(claim.basis.canonical_check.runner).toEqual({
      path: entryPath,
      sha256: createHash("sha256")
        .update(readFileSync(entryPath))
        .digest("hex"),
      version: packageValue.version,
    });

    const viteEntryPath = realpathSync(
      path.join(process.cwd(), "node_modules/vite/dist/node/index.js"),
    );
    const vitePackage = JSON.parse(
      readFileSync(
        path.join(process.cwd(), "node_modules/vite/package.json"),
        "utf8",
      ),
    ) as { version: string };
    expect(persisted.resolved_claim_report.report.producer.vite_loader).toEqual(
      {
        path: viteEntryPath,
        sha256: createHash("sha256")
          .update(readFileSync(viteEntryPath))
          .digest("hex"),
        version: vitePackage.version,
      },
    );
  });

  it("content-binds the exact validated owner bytes before enumeration", () => {
    const policyEngineRoot = path.resolve(process.cwd(), "../..");
    const ownerBytes = readFileSync(
      path.join(
        policyEngineRoot,
        "architecture/atlas_surfaces/live-application-readiness-ledger.json",
      ),
    );
    const digest = createHash("sha256").update(ownerBytes).digest("hex");
    expect(
      assertValidatedReadinessOwnerBytes(ownerBytes, digest, 261).entries,
    ).toHaveLength(261);
    const changedBytes = Buffer.from(ownerBytes);
    changedBytes[changedBytes.length - 2] ^= 1;
    expect(() =>
      assertValidatedReadinessOwnerBytes(changedBytes, digest, 261),
    ).toThrow(
      expect.objectContaining({ code: "canonical_owner_bytes_changed" }),
    );
  });

  it("binds both ledger-declared redirect endpoints to the imported runtime route", () => {
    expect(
      inspectAtlasRuntimeRedirect(
        {
          surface_id: "route-redirect-launch",
          title: "/launch to /compose",
        },
        APP_ROUTES,
      ),
    ).toMatchObject({ status: "matched", observed_to: "/compose" });
    expect(
      inspectAtlasRuntimeRedirect(
        {
          surface_id: "route-redirect-launch",
          title: "/launch to /wrong-target",
        },
        APP_ROUTES,
      ),
    ).toMatchObject({
      status: "mismatched",
      declared_to: "/wrong-target",
      observed_to: "/compose",
    });
  });

  it("gates the zero-instance stable arm identically to implemented", () => {
    const stableUnavailable = buildAtlasStableReadinessNegativeControl();
    if (stableUnavailable.basis.kind !== "observed_by_reconciler") {
      throw new Error("stable control must have an observed basis");
    }
    expect(stableUnavailable.basis.attestation_scope).toBe(
      OBSERVED_ATTESTATION_SCOPE,
    );
    const implementedUnavailable = observedVariant(
      observedClaim(persisted),
      "observation_unavailable",
    );

    expect(stableUnavailable).toMatchObject({
      dimension: "maturity",
      declared_value: "stable",
      predicate_provenance: "not_established",
      basis: {
        kind: "observed_by_reconciler",
        observation: {
          status: "observation_unavailable",
          reason: "canonical_stable_observer_not_registered",
        },
        canonical_check: {
          check_id: "surface-readiness.stable.maturity-prerequisite",
          runner: null,
          report_sha256: null,
          assertion_name: null,
          assertion_status: null,
          runtime_route: null,
        },
      },
    });
    expect(gateCode(stableUnavailable)).toBe(gateCode(implementedUnavailable));
    expect(gateCode(stableUnavailable)).toBe("claim_observation_unavailable");

    const dashboardRoot = process.cwd();
    const policyEngineRoot = path.resolve(dashboardRoot, "../..");
    const admissionWitness = `
import importlib.util
import json
import sys

module_path = sys.argv[1]
spec = importlib.util.spec_from_file_location("atlas_evidence_persistence", module_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
claim = json.load(sys.stdin)
source_projection, source_observation = module._health_source_projection()
_, node_executable, node_version = module._trusted_node()
expected_claim = {
    "claim_id": claim["claim_id"],
    "surface_id": claim["surface_id"],
    "title": claim["title"],
    "dimension": claim["dimension"],
    "declared_value": claim["declared_value"],
}
module._require_observed_readiness_basis(
    claim,
    expected_claim,
    source_projection=source_projection,
    source_validator_observation=source_observation,
    node_executable=node_executable,
    node_version=node_version,
)
print(json.dumps({"stable_basis": "admitted_as_unavailable"}))
`;
    const invokeAdmission = (claim: unknown) =>
      spawnSync(
        path.join(policyEngineRoot, ".venv/bin/python"),
        [
          "-I",
          "-c",
          admissionWitness,
          path.join(dashboardRoot, "scripts/persist_atlas_evidence.py"),
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
          input: JSON.stringify(claim),
          timeout: 30_000,
        },
      );
    const admission = invokeAdmission(stableUnavailable);
    expect(admission).toMatchObject({ status: 0, stderr: "" });
    expect(JSON.parse(admission.stdout)).toEqual({
      stable_basis: "admitted_as_unavailable",
    });

    const wrongScope = {
      ...stableUnavailable,
      basis: {
        ...stableUnavailable.basis,
        attestation_scope:
          "observed_by_reconciler attests unbounded runner integrity",
      },
    };
    const scopeRejection = invokeAdmission(wrongScope);
    expect(scopeRejection.status).not.toBe(0);
    expect(scopeRejection.stderr).toContain(
      "observed readiness basis attestation scope mismatch",
    );

    const wrongStableReason = {
      ...stableUnavailable,
      basis: {
        ...stableUnavailable.basis,
        observation: {
          status: "observation_unavailable",
          reason: "canonical_check_not_registered",
        },
      },
    };
    const stableRejection = invokeAdmission(wrongStableReason);
    expect(stableRejection.status).not.toBe(0);
    expect(stableRejection.stderr).toContain(
      "stable claim must fail closed while its canonical observer is absent",
    );
  });

  it("rejects a row with no basis or a second basis-shaped field", () => {
    const claim = observedClaim(persisted);
    const { basis: _basis, ...withoutBasis } = claim;
    expect(() => parseAtlasSurfaceReadinessClaim(withoutBasis)).toThrow();
    expect(() =>
      parseAtlasSurfaceReadinessClaim({
        ...claim,
        cited_basis: buildConsistentWithCitedReportClaim(
          claim,
          citedReportBytes("pass", []),
        ),
      }),
    ).toThrow();
  });

  it("makes the full canonical owner validator go red for a falsified constraint", () => {
    const dashboardRoot = process.cwd();
    const policyEngineRoot = path.resolve(dashboardRoot, "../..");
    const witness = `
import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

validator_path = sys.argv[1]
spec = importlib.util.spec_from_file_location("atlas_health_validator", validator_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
clean = module._load_json(module.REPO_ROOT / module.READINESS_PATH)
module.validate_owner_instance("readiness", clean)

additional = copy.deepcopy(clean)
additional["forged"] = True
duplicate = copy.deepcopy(clean)
duplicate["entries"].append(copy.deepcopy(duplicate["entries"][0]))

messages = []
for candidate, expected in (
    (additional, "Additional properties are not allowed"),
    (duplicate, "duplicate surface_id"),
):
    try:
        module.validate_owner_instance("readiness", candidate)
    except module.AtlasHealthSourceError as error:
        if expected not in str(error):
            raise SystemExit(f"wrong rejection: {error}")
        messages.append(str(error))
    else:
        raise SystemExit(f"constraint escaped: {expected}")

with tempfile.TemporaryDirectory() as directory:
    duplicate_json = Path(directory) / "duplicate.json"
    duplicate_json.write_text('{"entries": [], "entries": []}', encoding="utf-8")
    try:
        module._load_json(duplicate_json)
    except module.AtlasHealthSourceError as error:
        if "duplicate JSON key: entries" not in str(error):
            raise SystemExit(f"wrong duplicate-key rejection: {error}")
        messages.append(str(error))
    else:
        raise SystemExit("duplicate JSON key escaped")
print(json.dumps({"clean": "accepted", "targeted_rejections": messages}))
`;
    const result = spawnSync(
      path.join(policyEngineRoot, ".venv/bin/python"),
      [
        "-I",
        "-c",
        witness,
        path.join(dashboardRoot, "scripts/validate_atlas_health_sources.py"),
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
        timeout: 30_000,
      },
    );

    expect(result).toMatchObject({ status: 0, stderr: "" });
    const report = JSON.parse(result.stdout) as {
      clean: string;
      targeted_rejections: string[];
    };
    expect(report.clean).toBe("accepted");
    expect(report.targeted_rejections).toHaveLength(3);
  });

  it.each(["report", "exit_code", "basis", "root", "script"])(
    "rejects caller-supplied %s intake",
    (field) => {
      const result = invokePersistence(
        { operation: OPERATION, [field]: "supplied" },
        casRoot,
      );
      expect(result.status).toBe(1);
      expect(result.value).not.toHaveProperty("ok");
      expect(result.value.error).toMatchObject({
        code: "atlas_evidence_persistence_failed",
      });
    },
  );

  it("ignores inherited process-selection controls on the closed path", () => {
    const isolatedCas = mkdtempSync(
      path.join(tmpdir(), "atlas-readiness-env-cas-"),
    );
    try {
      const result = asProjectionResult(
        invokePersistence({ operation: OPERATION }, isolatedCas, {
          NODE_OPTIONS: "--require=/definitely/not/a/module.cjs",
          PATH: "/definitely/not/a/path",
          VITE_CONFIG: "/definitely/not/a/config.ts",
        }),
      );
      expect(result.resolved_projection.projection.claims).toHaveLength(5);
    } finally {
      rmSync(isolatedCas, { recursive: true, force: true });
    }
  }, 60_000);

  it("content-binds the exact per-row report bytes without a CI verdict", () => {
    expect(persisted.claim_report_ref.artifact_id).toBe(
      `sha256:${persisted.resolved_projection.projection.claim_report_sha256}`,
    );
  });
});
