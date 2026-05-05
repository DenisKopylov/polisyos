# Fabric Remediation Closure Matrix

This matrix tracks execution evidence for `FABRIC_AUDIT_REMEDIATION_PLAN.md`.

## Tranche 1

This implementation pass is the first closure tranche. It focuses on `Wave 0`
bootstrap items plus the highest-leverage fail-closed governance gap found in
the Fabric audit.

| Area                                              | Status      | Evidence                                                                                                                                                                         |
| ------------------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Wave 0 bootstrap                                  | Implemented | Root CI workflow adds Fabric remediation gates, repeated-run smoke, Fabric full-suite execution, and performance smoke coverage.                                                 |
| Strict provenance parser dependency               | Implemented | `rdflib` added to the `test` dependency set so strict N-Quads parsing now runs instead of being skipped.                                                                         |
| Broad-exception ratchet                           | Implemented | `scripts/testing/check_fabric_exception_baseline.py` tracks the current broad-exception baseline and fails on unreviewed drift.                                                  |
| Repeated race/leak runner                         | Implemented | `scripts/testing/repeat_pytest.py` provides the local/CI repeat harness requested by the remediation plan.                                                                       |
| Tenant-scope fail-closed world-query behavior     | Implemented | `world_query` now requires explicit enforced tenant scoping and rejects snapshot/non-tenant-aware backends.                                                                      |
| Pydantic `schema` shadowing warnings              | Implemented | Fabric contract models now use alias-backed internal field names while preserving external compatibility.                                                                        |
| Connector harness asyncio mark warnings           | Implemented | Harness no longer class-marks sync protocol checks with `pytest.mark.asyncio`.                                                                                                   |
| Warning baseline cleanup                          | Implemented | Connector loop fixture no longer uses deprecated event-loop policy APIs; strict provenance test uses modern `rdflib.Dataset`.                                                    |
| CAS/evidence governance metadata                  | Implemented | Artifact manifests now persist resolved classification, retention, and encryption metadata for evidence/provenance and world CAS writes.                                         |
| Cache retention/encryption enforcement            | Implemented | Cache payload/metadata writes now resolve governance from connector classification and fail closed when policy-required encryption is not verified.                              |
| World projection retention/encryption enforcement | Implemented | World snapshot records now persist governance metadata and reject governed snapshot writes when encryption requirements are unmet.                                               |
| Shared schema-governance evaluator                | Implemented | Runtime `ContractRegistry` and CI validation now use the same governance comparison logic for semver bumps, impacted surfaces, migration planning, and approval metadata checks. |
| Schema-governance CI evidence gate                | Implemented | Fabric remediation workflow now runs the schema governance check as a blocking step and uploads a machine-readable evidence artifact with impacted surfaces and migration plans. |

## Remaining Program Waves

All later phases remain open until code, tests, CI evidence, and acceptance
criteria are fully closed:

- `Phase 0-1` remaining hardening: bounded input last-mile cleanup, atomicity,
  resilience under contention, shared-state hardening, and bounded retrieval
  memory.

- `Phase 2-3` semantic correctness and governance: non-finite routing cleanup,
  lineage completeness and broader governance closure beyond the shared schema gate.

- `Phase 4-6` operational closure: quality gates, materialization/time-travel
  evidence, streaming/scale-out closure, and semantic/ER `v1` acceptance
  ratchets.
