---
title: OPS-R15 — Test and Probe Verification
status: draft_audit
kind: research-audit
research_task: OPS-R15
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
pao_r1_audit_commit: 566840c330e867a15313923c87c20b6863cb053f
audit_date: 2026-07-27
audit_branch: research/ops-r15-independent-audit
authoritative_for:
  - repository audit findings at recorded commits
  - benchmark-validity and executability findings
  - recommended corrections to OPS-R15
may_not_use_for:
  - production capability claim
  - legal compliance certification
  - final runtime contract
  - production RPO or RTO commitment
  - authority grant
  - implementation authorization
  - proof that an external institution performed an act
  - proof of disaster-recovery capability
research_only: true
---

# OPS-R15 Test and Probe Verification

## Scope and environment

All commands ran on branch `research/ops-r15-independent-audit` at `4813b49f6ce14e8debf3aaea096f0967d38d9768`. No production file was changed. Temporary analysis files were `/tmp/ops_r15_normalize.py`, `/tmp/ops_r15_probes.py`, `/tmp/generate_ops_r15_audit.py` and `/tmp/ops-r15-testenv`; none is committed.

The repository declares Python 3.14. The available executable was Python 3.12.13, so failing tests are recorded as **unresolved environment-sensitive signals**, not silently promoted to canonical repository defects. Passing tests demonstrate only their local contract.

## Commands and results

| # | Exact command | Result | What it proves / does not prove |
|---|---|---|---|
| 1 | `git rev-parse origin/main; git rev-parse HEAD; git show -s --format=%H 4813b49f6ce14e8debf3aaea096f0967d38d9768` | All `4813b49f6ce14e8debf3aaea096f0967d38d9768`. | Historical/current trees are identical for this audit; there is no stale-now class. |
| 2 | `cd policy-engine && python3 -m tools.cli workspace bootstrap` | Failed before bootstrap: `ModuleNotFoundError: click`. | Base environment was not repository-ready; no bootstrap success claim. |
| 3 | `cd policy-engine && python3 -m tools.cli workspace doctor` | Could not start in base environment for the same dependency reason. After temporary dependency installation, doctor reported nine issues, including Python 3.14 required versus 3.12.13 and Node 22.x required versus 24.14.0. | The prescribed environment was not reproducible here. |
| 4 | `python3 /tmp/ops_r15_normalize.py --json /workspace/scratch/d479b0fb609b/upload/OPS-R15_PolicyOS_Custody_Cycle_Capstone_Benchmark.md` | Completed. 117 unique calendar rows; 36 metrics; 20 gates; 15 wakes; 22 actors; 92 declared event types; 34 faults; 8 checkpoint rows. | Mechanical corpus counts and reference comparison; not semantic validity. |
| 5 | `/tmp/ops-r15-testenv/bin/python -m pytest -q tests/unit/runtime/http/test_control_plane_store.py` | 16 passed. | Local SQLite job/event/lease/outbox behavior; not tenant-bound custody or H2. |
| 6 | `/tmp/ops-r15-testenv/bin/python -m pytest -q tests/unit/scientist/orchestration/engine/test_checkpoint.py tests/unit/scientist/orchestration/engine/test_checkpoint_gc.py` | 40 passed, 1 failed. The failure imported JAX/jaxtyping code and raised `NameError: n_edges` under Python 3.12. | Checkpoint integrity/GC have substantial local tests; full resume suite was not green in the unsupported toolchain. |
| 7 | `/tmp/ops-r15-testenv/bin/python -m pytest -q tests/unit/fabric/data_plane/test_cursor_store.py tests/unit/fabric/data_plane/test_watermark.py tests/unit/fabric/mirror_contracts/test_temporal.py tests/unit/fabric/test_world_temporal_capabilities.py` | 34 passed. | Local cursor, watermark and temporal contracts; not a capstone world-release or bitemporal oracle. |
| 8 | `/tmp/ops-r15-testenv/bin/python -m pytest -q tests/unit/data_forge/legal_batch/test_jurisdictions.py tests/unit/data_forge/legal_batch/test_temporal_resolver.py` | 15 passed. | Current legal batch plugin/temporal behavior, including the behavior probed below; not jurisdiction-complete living law. |
| 9 | `/tmp/ops-r15-testenv/bin/python -m pytest -q tests/unit/scientist/mirror_contracts/test_decision_validity.py tests/unit/scientist/validation/test_decision_validity_service.py tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py tests/unit/core/artifacts/test_cas_integrity_report.py tests/unit/core/phase0/test_signing.py tests/unit/core/phase0/test_store_signing.py tests/unit/runtime/quality/test_external_audit.py` | 41 passed. | Local invalidation, lifecycle, partial reissue, CAS integrity, signing and external-audit projection contracts; not their end-to-end orchestration. |
| 10 | `/tmp/ops-r15-testenv/bin/python -m pytest -q -x tests/unit/runtime/http/test_governed_projection_service.py` (within the recorded three-file projection group) | Failed at `test_path_cache_detects_same_size_rewrite_with_preserved_mtime`: content hash remained unchanged. | An unresolved cache/filesystem-sensitive signal. It prevents a blanket “projection tests green” claim but is not attributed to OPS-R15 or declared a supported-toolchain defect. |
| 11 | `/tmp/ops-r15-testenv/bin/python -m pytest -q -x tests/unit/runtime/quality/test_multi_tenant_shared_cas.py` | First test passed; second failed because a raw tenant-private runtime ref remained in serialized public output. | A concrete negative result deserving owner reproduction on Python 3.14; it does not establish a cross-tenant read by itself. |
| 12 | `/tmp/ops-r15-testenv/bin/python -m pytest -q -x tests/unit/runtime/http/test_authorization_audience_denials.py` | First case returned fail-closed 503 contract violation instead of expected 403 permission denial. | Unsafe operation did not execute, but the contract suite was not green under this dependency/toolchain combination. |
| 13 | `env PYTHONPATH=src /tmp/ops-r15-testenv/bin/python /tmp/ops_r15_probes.py` | Completed; findings below. | Static/runtime shape probes only; no production capability proof. |
| 14 | `/tmp/ops-r15-testenv/bin/python -m pytest -q tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_lifecycle_drift_smoke.py` | 17 passed, 2 failed. The same two tests failed at the untouched baseline checkout: stale Atlas path findings and an expired docs-freshness exception baseline. | The failures pre-exist these audit files; this does not make the documentation gate green. |
| 15 | `/tmp/ops-r15-testenv/bin/python -m pytest -q tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_lifecycle_drift_smoke.py tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py` | 36 passed, 51 failed. Failures include the two baseline docs findings, wrong repository interpreter, absent `production_data`, Python-3.12/JAX typing errors, unconfigured LLM proof paths and existing artifact expectations. | Broad repo-quality execution was attempted and is not green in this environment; no failure is attributed to the seven Markdown files without an isolated causal witness. |

## Temporary probe results

| Probe | Exact result | Audit implication |
|---|---|---|
| Checkpoint security binding | `CheckpointMetadata` exposes 19 fields but no `tenant_id`, `cell_id` or `authority_boundary`. | Existing computational checkpoint is not sufficient evidence for exact custody resume. |
| Control-job security binding | `control_jobs` exposes job/run/pipeline/profile/payload/lease fields but no `tenant_id` or `cell_id`. | Generic control-plane persistence must not be called a tenant-bound H2 job store. |
| Jurisdiction fallback | Missing and unknown jurisdiction both resolve to `UA`. | OPS-R15’s “unknown jurisdiction fails closed” expectation contradicts this existing local behavior; the benchmark may require a future profile but cannot claim it exists. |
| Authority composition | Meet of `{claim:a, claim:b}` and `{claim:b, claim:c}` produced `{claim:b}`; denied uses unioned to `{individual_decision, payment}`; grade/posture weakened. | `AuthorityBoundary` supplies a real narrow grammar suitable for reuse. |
| Same-code rebuild | Deliberately faulty reducer produced `3` incrementally and `3` on rebuild while the independent correct result was `103`. | Parity of the same reducer is circular and can reproduce a semantic defect exactly. |

## Existing capability evidence

| Primitive | Representative repository evidence | Actual state | What is missing for OPS-R15 |
|---|---|---|---|
| Control job/lease/outbox | `src/polisyos/runtime/http/services/control_plane_store.py`; `test_control_plane_store.py` | `implemented` for local scope | tenant/cell/matter binding, custody resume semantics, end-to-end consumer |
| Scientist checkpoint/resume | `src/polisyos/scientist/orchestration/engine/checkpoint.py` | `implemented` for computational workflow | authority re-admission, exact tenant/cell closure, generic custody waits |
| CAS and manifests | `src/polisyos/core/artifacts`; integrity tests | `implemented` locally | cross-store recovery oracle and capstone bridges |
| Fabric cursor/watermark/temporal | data-plane and mirror contracts/tests | `implemented` locally | one governed bitemporal custody model and family bridges |
| AuthorityBoundary | `src/polisyos/pdc/_impl/layer2_readiness.py` | `implemented` | longitudinal external-evidence impact orchestration |
| Decision-Validity/lifecycle | core contracts + Scientist services/tests | `implemented_but_not_orchestrated` | fleet/matter/public fan-out |
| Legal plugins | `src/polisyos/data_forge/domains/legal/batch/jurisdictions` | `implemented` for EU/UA local batch scope | unknown-jurisdiction fail-closed behavior and continuous legal release |
| Audit/signing | core audit/phase0 tests | `implemented` for narrow artifacts | long-term preservation/revocation/public verification profile |
| Public projection | runtime/PDC contracts and tests | `partial_internal_owner` | one controlled-surface inventory and current/correction parity |
| `PolicyMatter` | absence census | `planned/research_only` | production identity and lineage |
| Operational boundary register | absence census + PAO-R1 audit | `research_only` | consolidated invariant/owners; full register rejected |
| `WorldRelease` | plans/research only | `planned_only` | schema, producer, compatibility oracle, head owner |
| H2 | plans/research only | `planned_only` | every capstone end-to-end bridge |

## Reproducible absence census

Baselines A and B are the same commit, so each query was evaluated once against `4813b49f6ce14e8debf3aaea096f0967d38d9768` and applies identically to both.

| Absence claim | Exact query | Paths / exclusions | Result | Confidence / blind spots |
|---|---|---|---|---|
| No named production matter, boundary, world-release or custody-resume contract | `git grep -n -E '(CaseSuspensionRecord\|CaseResumeReceipt\|OperationalEventEnvelope\|WorldRelease\|OperationalBoundaryDecision\|PolicyMatter)' 4813b49f6ce14e8debf3aaea096f0967d38d9768 -- policy-engine/src policy-engine/tests` | Tracked `src` and tests; docs intentionally excluded from production-symbol claim | No matches | High for exact names; medium for semantic equivalents under unrelated names. |
| No named OPS-R15 fixture/receipt implementation | `git grep -n -E '(CapstoneScenarioManifest\|CapstoneEventFixture\|ExpectedCustodyTrace\|CapstoneRunReceipt\|BoundaryViolationReceipt\|ReplayParityReceipt)' 4813b49f6ce14e8debf3aaea096f0967d38d9768 -- policy-engine/src policy-engine/tests` | Tracked source/tests only | No matches | High for exact report sketches; does not prove absence of generic test infrastructure. |
| Named concepts occur only as research/decision language | `git grep -n -E '\b(PolicyMatter\|OperationalBoundaryDecision\|WorldRelease)\b' 4813b49f6ce14e8debf3aaea096f0967d38d9768 -- policy-engine/src policy-engine/tests policy-engine/architecture policy-engine/docs` | Tracked text; binaries, external services and untracked files excluded | Matches only the operations backlog and identity/custody decision; none in source/tests | High for tracked tree; external/untracked systems unavailable. |
| No executable supplied capstone artifact | `rg -n '(CapstoneScenarioManifest\|ExpectedCustodyTrace\|CCB24-001)' policy-engine/src policy-engine/tests` | Current checkout source/tests; generated build output and external CI artifacts excluded | No matches | High for repository runner/fixtures; attachment itself is outside repository. |

A failed name search is not semantic proof. These claims are limited to the exact symbols and tracked paths. The audit also inspected owner-adjacent generic checkpoint, control, temporal, lifecycle, audit and projection implementations to avoid converting missing names into missing capability by assumption.

## Mandatory probe disposition

| Requested probe | Result |
|---|---|
| Generic resume bypasses authority reproof | Existing checkpoint resume has no authority-boundary field or universal reproof; bypass is **not executable as a capstone proof** and remains a high-risk missing bridge. |
| Checkpoint preserves tenant/cell | No such fields in checkpoint metadata; not supported. |
| Payload-identical authority revocation | `AuthorityBoundary` can narrow; no end-to-end reuse invalidation chain found. |
| Unknown jurisdiction fallback | Defaults to UA in inspected batch registry; contradicts fail-closed benchmark expectation. |
| Event order changes semantics | Existing local event models vary; OPS-R15 supplies no executable partial-order oracle. |
| Duplicate irreversible effects | Control-store idempotency tests pass locally; no cross-family irreversible-action test. |
| Late correction rewrites history | Append-only lifecycle tests exist; full public/historical path absent. |
| Public remains current after supersession | Projection semantics exist; no complete controlled-surface fan-out test. |
| Workflow/validator drift visible to dormant cases | Workflow fingerprint is present; no custody-wide wake/revalidation chain. |
| Latest-of-each world vector | No production `WorldRelease`; fixture-only. |
| Same-code rebuild defect | Demonstrated: parity masked the injected defect. |
| Unscoped lifecycle event | Existing lifecycle services have blockers; no matter-scoped capstone. |
| Wrong-claim evidence | Purpose boundary exists; institutional admission bridge absent. |
| Wrong-tenant evidence | Tenant tests exist but one public-redaction test failed in this environment; end-to-end admission unavailable. |
| Signature valid while authority stale | Cryptographic/semantic layers are separate; no capstone chain. |
| Cross-surface status | No frozen surface inventory or executable cross-surface oracle. |
| Administrative verbs conceal act | Static corpus examples demonstrate risk; no runtime administrative-act linter/adapter block. |
| ID branching / adjacent case | No benchmark runner or hidden fixture system; conceptual only. |
| Missing affected edge | No independent affected-set oracle. |
| Asymmetric CAS/control snapshots | No defined executable reconciliation harness. |
| Existing tests support full baseline | They support local primitives only; no end-to-end OPS-R15 capability. |

## Mechanical corpus verification

- Frontmatter parses and records `accepted_narrow_scope`.
- The calendar contains 117 unique IDs: numeric sequence 001–115 plus `064A` and `094A`; no numeric gaps or duplicates.
- The event-type dictionary has 92 names; 87 calendar event names are not literal dictionary members and 62 dictionary names are unused literally. This is a normalization defect, not necessarily 149 semantic event families.
- All calendar rows have visible expected answers, producing universal leakage if supplied unchanged to an implementation.
- Every row’s oracle is a prose label, not a resolvable machine-readable oracle artifact.
- Failure-pattern IDs resolve at both identical baselines; Appendix H’s `Detected` label describes proposed coverage, not executed detection.

## Missing semantic tests

No existing test independently establishes:

- exact end-to-end wake binding across external evidence/admission/H2;
- one resume generation across distributed duplicate delivery;
- payload-identical authority revocation invalidating every affected claim;
- implementation-independent current rebuild;
- transaction-time replay with historical validator/rule/identity/boundary versions;
- complete matter/fleet/public affected-set recall;
- external act never invoked by H2;
- sealed adjacent-case and ID-permutation resistance;
- asymmetric CAS/control-store recovery;
- full controlled-surface currentness and correction parity.

## Environmental limitations

The required Python 3.14 and Node 22.x toolchain was unavailable (the host provided Python 3.12.13 and Node 24.14.0). Dependencies were installed into an isolated temporary Python 3.12 environment, so failures may reflect version or filesystem differences. No networked external institution, production topology, KMS, partner API, distributed scheduler, browser surface set or sealed oracle service was available. No RPO/RTO or production-recovery claim was tested.
