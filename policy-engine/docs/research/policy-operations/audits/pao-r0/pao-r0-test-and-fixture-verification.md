---
title: PAO-R0 — Test and Fixture Verification
status: draft_audit
kind: research-audit
research_task: PAO-R0
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
audit_date: 2026-07-26
audit_branch: research/pao-r0-independent-audit
authoritative_for:
  - repository audit findings at the recorded commits
  - recommended research corrections
may_not_use_for:
  - production capability claim
  - final code contract
  - authority grant
  - production migration authorization
  - automatic identity adjudication
  - direct modification of authoritative plans
research_only: true
---

# PAO-R0 — Test and Fixture Verification

## 1. Verification standing

This record distinguishes:

- tests that ran under the repository-prescribed environment;
- tests that ran under a bounded audit-only Python environment;
- failures caused by audit shims or missing dependencies;
- reproducible baseline failures;
- static probes that do not prove runtime behavior.

Historical and current baselines are the same Git tree:
`4813b49f6ce14e8debf3aaea096f0967d38d9768`. Dynamic commands were run once on the pinned
current checkout. Their test definitions are identical at the historical baseline, but
environmental execution was not repeated in a second worktree.

No production code or repository test was edited. Temporary dependency environments and
the import shim lived under `/tmp` and are not committed.

## 2. Environment and bootstrap

| Command | Result | Audit relevance |
| --- | --- | --- |
| `cd policy-engine && python3 -m tools.cli workspace bootstrap` | Exit 1: `ModuleNotFoundError: No module named 'click'`. | The prescribed bootstrap cannot start under system Python. |
| `cd policy-engine && python3 -m tools.cli workspace doctor` | Exit 1: same missing `click`. | No doctor result may be claimed from system Python. |
| `cd policy-engine && /tmp/pao-r0-testenv/bin/python -m tools.cli workspace doctor` | Partial run. Python 3.14.6, uv 0.9.21, and `uv.lock` checks passed. Node 24.14.0 did not match expected 22; Playwright Chromium was absent; corepack could not create `/root/.cache/node/corepack/v1`; dependency synchronization retried and was interrupted. | Documents environment limits; not a PAO-R0 semantic failure. |
| `cd policy-engine && UV_CACHE_DIR=/tmp/pao-r0-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/pao-r0-uv-python uv run pytest tests/unit/pdc tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py tests/repo_quality/tools/test_compiled_pdc_graph_smoke.py -q` | Dependency sync blocked: `pillow==10.4.0` lacked a compatible wheel for the selected Python and JPEG build headers were unavailable. | The PDC README verification command did not run; no full-suite pass is claimed. |

The bounded audit environment used Python 3.14.6 and only the packages needed for selected
tests. An import shim at `/tmp/pao-r0-stubs/sitecustomize.py` prevented
`polisyos.runtime.quality` and Foundry's package initializers from eagerly importing unrelated
heavy dependencies. The shim did not modify repository files. Results that depended on
shimmed exports are identified below.

## 3. Commands executed and results

### 3.1 PDC graph and projection

```text
PYTHONPATH=/tmp/pao-r0-stubs:src:. \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q \
  tests/unit/pdc/test_runtime_policy_design_case_compiler.py
```

Result: **4 passed**.

Properties exercised:

- runtime graph construction from actual typed source inputs;
- projection source remains projection-only;
- graph persistence in CAS;
- direct LLM-candidate laundering is rejected.

```text
PYTHONPATH=/tmp/pao-r0-stubs:src:. \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py
```

Result: **37 passed**.

Properties exercised:

- projections do not mint claim/closeout authority;
- missing blockers, contested state, omission manifests, and reconstructable references fail;
- simulation-only and candidate-only inputs cannot become current evidence authority.

These tests prove PDC projection and authority-boundary behavior. They do not prove a
matter identity, case-to-matter association, split/merge, namespace federation, or
matter-aware correction.

### 3.2 Targeted fixture/capability batch

```text
PYTHONPATH=/tmp/pao-r0-stubs:src:. \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q \
  tests/unit/runtime/quality/test_policy_design_case_record_registry.py \
  tests/unit/runtime/quality/test_tenant_cas_approval_governance.py \
  tests/unit/runtime/quality/test_multi_tenant_shared_cas.py \
  tests/unit/scientist/validation/test_decision_validity_service.py \
  tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py \
  tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py \
  tests/unit/fabric/test_lex_corpus.py \
  tests/unit/core/phase0/test_audit_export_verify.py \
  tests/unit/ir/test_policy_portfolio.py
```

Result: **54 passed, 1 failed**.

The failure was:

```text
tests/unit/runtime/quality/test_multi_tenant_shared_cas.py::
  test_public_export_redacts_tenant_private_runtime_refs_from_payload_and_projection
```

The first assertion failed because the raw tenant-private
`sha256:8888…8888` reference remained in serialized public output. This was rerun alone and
failed identically. The test exercises the real `build_public_export_bundle`; the import shim
does not replace that function. It is therefore recorded as a reproducible repository
baseline failure, not an environmental failure.

The neighboring cross-tenant access test was rerun separately:

```text
PYTHONPATH=/tmp/pao-r0-stubs:src:. \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q \
  tests/unit/runtime/quality/test_multi_tenant_shared_cas.py::
  test_shared_cas_blocks_cross_tenant_runtime_lineage_scorecard_approval_and_export_reads
```

Result: **1 passed**. This proves CAS ownership checks for the exercised flow. It does not
cancel the public-export redaction defect.

### 3.3 PDC directory

```text
PYTHONPATH=/tmp/pao-r0-stubs:src:. \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q tests/unit/pdc
```

Result: **122 passed, 1 failed**.

The failure,
`test_design_record_maturity_report_requires_s2_s5_s8_refs_for_s9`, attempted to access
`runtime_quality.DesignRecordMaturityReport` through the package facade. The audit shim
intentionally replaced that eager facade and did not export the symbol. This result is
classified **environment/shim-induced** and does not alter a PAO-R0 verdict.

### 3.4 DDM

```text
PYTHONPATH=/tmp/pao-r0-stubs:src:. \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q \
  tests/unit/ddm/test_facade.py \
  tests/unit/ddm/test_readiness_mapping.py
```

Result: **4 passed**.

The tests prove selected DDM public/readiness behavior. They do not show any matter
association or identity adjudication.

### 3.5 Signing and offline audit

```text
PYTHONPATH=/tmp/pao-r0-stubs:src:. \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q \
  tests/unit/core/phase0/test_signing.py::test_sign_verify_roundtrip_valid \
  tests/unit/core/phase0/test_store_signing.py::test_verify_signature_valid \
  tests/unit/core/phase0/test_audit_export_verify.py::test_audit_export_and_verify_full
```

Result: **3 passed**.

The signing statement binds `artifact_id`, blob hash, manifest hash, and key ID. The tests
prove byte/manifest integrity and portable verification, not the semantic correctness of a
future matter association.

### 3.6 Runtime lineage

```text
PYTHONPATH=src:. \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q \
  tests/unit/runtime/http/test_lineage_api.py \
  tests/unit/runtime/http/test_lineage_routes.py
```

Result: **collection blocked**.

The runtime HTTP fixture imports the application, which imports Foundry agent-simulation
modules through runtime quality. Installed `jax` then failed because `jaxlib` was unavailable.
No runtime-lineage pass/fail conclusion is drawn.

### 3.7 Architecture guardrails

```text
PYTHONPATH=.:/tmp/pao-r0-stubs:src \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q \
  tests/repo_quality/architecture/test_arch_import_gate.py \
  tests/repo_quality/architecture/test_public_surface_snapshot.py \
  tests/repo_quality/architecture/test_public_api_facades.py
```

Result: **2 passed, 2 failed**.

- `test_arch_import_gate` found current forbidden/deep imports, many after exception expiry
  on 2026-07-01, plus current unexcepted violations.
- `test_public_surface_snapshot_gate_matches_phase3a_baseline` found snapshot drift.
- two public-facade checks passed.

These failures are repository-wide baseline debt, not caused by PAO-R0. They reinforce the
need for explicit owner/public-surface review before a new cross-package contract.

### 3.8 PDC compiled smoke

The compiled smoke test was attempted with the import shim. It failed because a shimmed
Foundry normalization helper returned a shape that the smoke path classified as blocked.
The result is **non-authoritative/environment-altered** and is not used as repository
evidence.

### 3.9 Documentation quality gates

```text
PYTHONPATH=.:/tmp/pao-r0-stubs:src \
  /tmp/pao-r0-testenv/bin/pytest -c /dev/null -q \
  tests/repo_quality/tools/test_docs_gate.py \
  tests/repo_quality/tools/test_docs_lifecycle.py
```

Result: **31 passed, 2 failed**.

The failures came from the baseline lifecycle checker:

- stale `frontend/runtime-dashboard` references in an existing Atlas adoption ledger;
- an expired docs-freshness exception baseline.

Neither failure names the new PAO-R0 directory. They are recorded as repository baseline
debt rather than audit-artifact defects.

## 4. Exact fixture and test inventory

| Report reference | Baseline A | Baseline B | Exact path/symbol | What it proves | What it does not prove | Reuse verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `run-24` | Exists as a literal | Same | `tests/unit/pdc/test_runtime_policy_design_case_compiler.py::test_runtime_policy_design_case_compiler_uses_existing_runtime_surfaces` | One PDC graph compile scenario. | It is not a fixture symbol, frozen corpus, case identity, or matter graph. | Reuse builder/test pattern; rename the report claim. |
| PDC projection tests | Exist | Same | `tests/unit/pdc/test_runtime_policy_design_case_compiler.py::test_runtime_policy_design_case_projection_is_projection_only`; `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py::*` | Projection-only/anti-authority properties. | No matter semantics or public correction. | Legitimate property patterns. |
| PDC anti-LLM laundering | Exists | Same | `test_runtime_policy_design_case_compiler_rejects_llm_candidate_laundering`; projection laundering tests | Candidate output cannot directly become authority. | It does not validate identity evidence. | Legitimate negative pattern. |
| PDC record-family completeness | Exists | Same | `test_minimum_record_registry_covers_every_sdd_family_with_typed_evidence`; `test_policy_design_case_status_pass_cannot_replace_runtime_record_families` | Status-only pass cannot replace required typed records. | No subject/matter closure. | Legitimate gate pattern. |
| Tenant/CAS isolation | Exists | Same | `test_shared_cas_blocks_cross_tenant_runtime_lineage_scorecard_approval_and_export_reads` | Exercised cross-tenant CAS reads/writes are blocked; identical bytes retain same content ID. | Federated matter equality, tenant transfer, public redaction. | Reuse isolation pattern; do not assume IDs differ by tenant. |
| Public tenant-ref redaction | Exists but red | Same | `test_public_export_redacts_tenant_private_runtime_refs_from_payload_and_projection` | Intended to prove private refs are absent. | Currently proves the property is not satisfied. | Blocker, not reusable green evidence. |
| Recall/retraction | Exists | Same | `tests/unit/runtime/quality/test_tenant_cas_approval_governance.py::test_scorecard_blocks_recall_retraction_without_public_contestability` | Missing public contestability blocks scorecard. | No matter correction/fan-out. | Reuse blocker pattern. |
| `lineage_fixture_001` | Exists as a literal | Same | `tests/unit/scientist/validation/test_decision_validity_service.py::test_decision_validity_service_records_events_dedupes_and_tracks_monitoring` | Law-change event, dedupe, state transition, monitoring job. | Not a named fixture, tenant scope, matter identity, or generic authority-loss split. | Reuse test pattern; rename claim. |
| Legacy decision packet | Exists | Same | `test_decision_validity_service_applies_sticky_triggers_to_legacy_packets` | Sticky trigger applies to a legacy packet. | Matter migration or signed historical association. | Reuse migration pattern only. |
| Partial reissue | Exists | Same | `test_partial_scope_builder_maps_monitor_event_and_preserves_unaffected_refs`; `test_partial_scope_builder_rejects_unscoped_detector_event` | Affected scope is required; unaffected refs survive. | Matter split/merge or identity correction. | Strong append-only/scoping precedent. |
| Lifecycle bridge | Exists | Same | `test_bridge_maps_detector_families_to_claim_lifecycle_and_public_revision`; `test_bridge_reissued_transition_uses_partial_reissue_packet_and_persists_result`; `test_unscoped_detector_event_produces_missing_lifecycle_bridge_blocker` | Detector → claim lifecycle bridge and unscoped-event blocker. | Matter-wide orchestration or historical bitemporal replay. | Strong claim-level pattern. |
| Lex version selection | Exists | Same | `tests/unit/fabric/test_lex_corpus.py::test_lex_resolve_active_version_is_deterministic`; `...does_not_fallback_to_published_at_only` | Deterministic legal version selection and effective-date discipline. | Policy continuity or sole Lex ownership of the producer. | Reuse legal-document evidence pattern. |
| Runtime `valid_at`/`tx_at` lineage | Tests exist | Same | `tests/unit/runtime/http/test_lineage_api.py::test_runtime_lineage_endpoint_returns_compact_and_full_graph`; `...test_runtime_lineage_exports`; route tests | Intended artifact/run lineage temporal/export behavior. | Did not execute in audit environment; no matter graph. | Static evidence only in this audit. |
| Audit export/offline verification | Exists and selected test passed | Same | `tests/unit/core/phase0/test_audit_export_verify.py::*` | Integrity/signature/provenance archive verification. | Semantic correctness or custody event ownership. | Reuse packaging/verifier pattern. |
| PolicyPortfolio negative | Portfolio tests exist | Same | `tests/unit/ir/test_policy_portfolio.py::*`; ADR-0022 | Candidate portfolio composition and interaction semantics. | Tests do not explicitly assert “not deployed identity.” | Conceptual negative evidence, not a fixture. |
| Artifact-lineage closure | Tests/code exist, no named fixture | Same | `src/polisyos/ir/artifacts/lineage.py`; artifact inspector/IR tests | Technical CAS/task dependency graph. | Policy relation types or competence. | Reuse technical dependency substrate only. |

## 5. Claimed fixture verdicts

Confirmed:

- the named test families exist;
- PDC anti-laundering and record completeness are real negative gates;
- decision validity responds to law/context changes;
- partial reissue and lifecycle bridges preserve unaffected records and block unscoped events;
- legal version selection is deterministic and effective-date aware;
- audit archives can be verified offline;
- PolicyPortfolio is semantically a candidate portfolio.

Rejected or qualified:

- `run-24` is not a fixture object;
- `lineage_fixture_001` is not a fixture object;
- there is no frozen PolicyMatter semantic corpus;
- there is no PolicyPortfolio “non-identity” fixture;
- there is no reusable split/merge/succession matter fixture;
- current public-export redaction is not green;
- runtime-lineage tests were not executable in the audit environment;
- no existing fixture establishes matter-aware public correction or historical identity replay.

## 6. Gaps between proposed benchmark and repository fixtures

| Proposed benchmark property | Closest repository test | Gap |
| --- | --- | --- |
| Same name, unrelated matter | PDC anti-laundering | No matter pair, authority evidence, or false-merge oracle. |
| Pilot → national continuity | None | Requires external competence and evidence-scope model. |
| Split/merge parent preservation | Partial reissue/artifact lineage | No identity cardinality or parent matter IDs. |
| Unresolved/contested identity | Existing contested claim/capability statuses | Mapping could create a parallel lattice; no resolution artifact. |
| Cross-tenant external-ID collision | Shared-CAS test | CAS intentionally shares content IDs; no external/matter namespace. |
| Wrong matter public correction | Recall/retraction/public export | No matter ref or correction feed; redaction test currently fails. |
| Pre-correction replay | Fabric/runtime bitemporal tests | No historical case-to-matter association. |
| Evidence transport after continuity | Transportability/applicability tests | No identity-to-transport firewall integration. |
| Malicious merge/split | Governance/adversarial tests in other domains | No privileged matter operation or reviewer packet. |
| Key rotation + wrong association | Signing/audit tests | Integrity only; semantic correction after rotation unimplemented. |

## 7. Proposed fixture mapping

A later, separately approved benchmark can reuse the following **patterns**, not the literal
fixtures as-is:

| Proposed family | Repository seed | Required new semantic layer |
| --- | --- | --- |
| `PM-ID-*` identity outcomes | PDC compiler builders and strict models | Independent matter ground truth, competent evidence, relation/outcome mapping. |
| `PM-META-*` metamorphic checks | PDC anti-laundering and status-only rejection | Generic mutation generator; verify property, not fixture strings. |
| `PM-MIG-*` migration/replay | decision validity legacy packet, partial reissue, CAS signing | Additive association artifacts, old/new temporal views, byte/hash equality. |
| tenant/federation sentinels | shared CAS ownership test | Matter namespace separate from content identity; tenant-qualified stores/routes/caches. |
| public correction sentinels | recall/retraction and public export | PAO-R36 correction chain, cache/API/archive/translation consumers. |
| offline verification | core audit round trip | Semantic assertion verifier from the future canonical producer. |

Before use, the corpus must:

1. be independently adjudicated and sealed;
2. distinguish `unresolved`/`contested` as resolution outcomes, not truth labels generated by
   the same resolver;
3. contain adversarial variants, not just the examples in PAO-R0;
4. prove its verifier fails after property corruption;
5. avoid hard-coding expected behavior for jurisdiction-dependent split/merge cases;
6. remain explicitly synthetic/non-authoritative.

## 8. Adversarial probes

| Probe | Method and outcome | Verdict |
| --- | --- | --- |
| 1. Remove decisive authority evidence but keep schema markers | Existing record-family and projection tests reject status-only/marker-only authority and passed. No matter evidence type exists to remove. | Existing generic gate confirmed; matter-specific probe impossible. |
| 2. Treat generic metadata as identity evidence | Exact search found no `same_policy`/matter consumer. PDC models use `extra="forbid"`; arbitrary CAS payloads can contain metadata but no current path admits it as matter identity. | No current exploit path; future contract still needs typed allowlisting. |
| 3. Projection mints authority | PDC projection negatives passed. Active Atlas plan and code show local readiness synthesis remains in two surfaces. | Backend PDC gate strong; UI projection-only compliance incomplete. |
| 4. Identical IDs collide across tenants | Shared CAS intentionally produces identical `ArtifactID` for identical bytes while ownership gates access. `DecisionValidityStateStore` maps identical raw lineage keys to the same path and has no tenant parameter. | Content-ID equality is safe by design; decision-lineage key collision risk confirmed for shared store. |
| 5. Correct public artifact without changing bytes | Signing statement binds blob and manifest hashes; modifying either invalidates verification. No matter correction sidecar/consumer exists. | Historical bytes can remain; sufficiency of sidecar is unproven. |
| 6. Distinguish payload-invalid from authority-invalid | Decision validity carries dependencies/reasons/status but no canonical two-set output. OPS-R2 explicitly plans `payload_recompute_set` vs `authority_revalidation_set`. | Planned, not implemented as claimed capability. |
| 7. Lifecycle correction preserves replay | Partial reissue/lifecycle tests preserve old/unaffected refs and use append-only transitions. No matter bitemporal correction path exists. | Claim-level precedent only. |
| 8. Existing split/merge lineage without provenance collapse | IR lineage supports artifact/task relations only; lifecycle/reissue is claim scoped. | Matter split/merge not representable by current canonical primitives. |
| 9. One PDC relates to multiple subjects | Runtime PDC fields contain no case/matter/subject field; model is strict with `extra="forbid"`. | Current graph cannot express either one or many matter subjects; cardinality remains open. |
| 10. APIs assume case/run/decision as top subject | Generated clients expose many `/api/v1/runs/{run_id}/…` paths; PDC records expose `case_id`; validity DTOs expose `decision_lineage_key`. | Migration blast radius confirmed; none is explicitly documented as lifetime policy identity. |
| 11. Named fixture existence | Exact-symbol and literal search performed. `run-24` and `lineage_fixture_001` are literals. | Fixture claim rejected/qualified. |
| 12. PolicyPortfolio confused with deployed identity | ADR/code define candidate `PolicySpec` portfolios. Tests validate composition but no explicit anti-identity guard exists. | Semantic distinction confirmed; adversarial guard absent. |
| 13. Hidden/unregistered dependency escapes fan-out | Current technical lineage can only traverse registered manifest/task edges. OPS-R2 calls hidden dependencies a falsifier and is planned only. | Matter-aware completeness unproven. |
| 14. Public URL/dashboard query embeds run/case identity | Generated clients/dashboard routes are run-oriented; current cache/index code keys by `run_id`; case and decision IDs appear in DTOs. | Structural migration risk confirmed; no matter route exists. |

### Decision-lineage collision probe command

```text
PYTHONPATH=/tmp/pao-r0-stubs:src \
  /tmp/pao-r0-testenv/bin/python - <<'PY'
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from polisyos.scientist.validation.decision_validity import DecisionValidityStateStore
with TemporaryDirectory(prefix="pao-r0-probe-") as root:
    store = DecisionValidityStateStore(SimpleNamespace(root=root))
    a = store._lineage_path("shared-lineage")
    b = store._lineage_path("shared-lineage")
    print(a == b, a)
PY
```

Outcome: `True`; the path is
`<root>/decision_validity/lineages/<sha256-of-raw-key>.json`.

### PDC subject-cardinality probe command

```text
PYTHONPATH=/tmp/pao-r0-stubs:src \
  /tmp/pao-r0-testenv/bin/python - <<'PY'
from polisyos.pdc import RuntimePolicyDesignCase
fields = set(RuntimePolicyDesignCase.model_fields)
print(fields & {"subject_id", "subject_ref", "matter_id", "matter_ref", "matter_refs",
                "policy_matter_id"})
print(RuntimePolicyDesignCase.model_config.get("extra"))
PY
```

Outcome: empty set and `forbid`.

## 9. Probes not possible

- A true matter split/merge/reconciliation replay: no matter contract or producer exists.
- Cross-institution matter federation: no namespace/trust protocol or external registry.
- Public wrong-matter correction after key rotation: no matter correction chain.
- Runtime lineage API execution: environment lacks `jaxlib`.
- Full workspace bootstrap/doctor and frozen PDC command: environment cannot complete
  dependency synchronization.
- Production cache collision or public URL invalidation: no deployed cache/service access.
- Jurisdiction-specific competence adjudication: requires external legal evidence and a
  ratified competence model.

## 10. Runtime-verification blockers

| Blocker | Effect on conclusions |
| --- | --- |
| System Python lacks `click` | Prescribed CLI commands do not start. |
| Pillow/JPEG build unavailable | Frozen `uv run` suite cannot synchronize. |
| `jaxlib` unavailable | Runtime HTTP lineage tests cannot collect. |
| Playwright Chromium absent | Browser/surface diagnostics cannot execute. |
| Node 24 vs expected 22 | Frontend reproducibility is not established. |
| Corepack cache path unavailable | `pnpm`/frontend checks cannot run normally. |
| No deployed external services | Static findings cannot prove production behavior. |
| No PolicyMatter implementation | Matter-specific semantic probes are necessarily design/absence findings. |

These blockers lower confidence only for runtime behavior they directly prevent. They do not
affect high-confidence static findings such as identical baseline SHAs, absence of matter
symbols, exact owner/readme text, failure-pattern definitions, strict model fields, signature
payload construction, or raw decision-lineage key path construction.
