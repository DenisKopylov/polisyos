import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterAll, describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/app/routes/routes";

import {
  assertAtlasSurfaceReadinessClaimForCi,
  assertValidatedReadinessOwnerBytes,
  AtlasSurfaceReadinessContractError,
  type AtlasSurfaceReadinessClaim,
  buildConsistentWithCitedReportClaim,
  inspectAtlasRuntimeRedirect,
  parseAtlasSurfaceReadinessClaim,
} from "./atlasSurfaceReadinessReconciliation";

const OPERATION = "persist_atlas_surface_readiness_claims";

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
    report: { claims: AtlasSurfaceReadinessClaim[] };
  };
  resolved_projection: {
    artifact_id: string;
    projection: {
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

function gateCode(value: unknown): string | null {
  try {
    assertAtlasSurfaceReadinessClaimForCi(value);
    return null;
  } catch (error) {
    expect(error).toBeInstanceOf(AtlasSurfaceReadinessContractError);
    return (error as AtlasSurfaceReadinessContractError).code;
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
  const independentlyDiscoveredClaims =
    persisted.resolved_projection.projection.claims.map(
      (claim) => [claim.claim_id, claim] as const,
    );

  it("enumerates the complete gated owner set through the admitted projection", () => {
    expect(persisted.operation).toBe(OPERATION);
    expect(independentlyDiscoveredClaims).toHaveLength(5);
  });

  it.each(independentlyDiscoveredClaims)(
    "CI independently gates %s without changing artifact bytes",
    (_claimId, claim) => {
      const artifactsWithoutGate = JSON.stringify({
        report: persisted.resolved_claim_report.report,
        projection: persisted.resolved_projection.projection,
      });

      expect(() => assertAtlasSurfaceReadinessClaimForCi(claim)).not.toThrow();
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
    expect(gateCode(cited)).toBe("cited_report_not_observation");
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
    const implementedNegative = observedVariant(
      observedClaim(persisted),
      "not_observed",
    );
    const stableNegative = {
      ...(implementedNegative as Record<string, unknown>),
      claim_id: "synthetic-stable-negative-control:maturity:stable",
      surface_id: "synthetic-stable-negative-control",
      title: "Synthetic stable negative control",
      dimension: "maturity",
      declared_value: "stable",
    };

    expect(parseAtlasSurfaceReadinessClaim(stableNegative)).toMatchObject({
      dimension: "maturity",
      declared_value: "stable",
    });
    expect(gateCode(stableNegative)).toBe(gateCode(implementedNegative));
    expect(gateCode(stableNegative)).toBe("canonical_claim_not_observed");
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
    expect(report.targeted_rejections).toHaveLength(2);
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
