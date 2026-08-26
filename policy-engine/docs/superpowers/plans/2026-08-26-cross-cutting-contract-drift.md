# Cross-Cutting Canonical Interface Contract Drift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the `polisyos.core.security`, `polisyos.core.trace`, and `polisyos.common.config` canonical-interface contract drift without publishing deep submodules, while registering and sizing the deferred `polisyos.core.observability` member of the same class.

**Architecture:** Reconcile the ratified cross-cutting-concern decisions with the primary package contracts and their exhaustive public-surface aggregate mirror, then route cross-package consumers through the canonical root facades. Preserve one explicit, registered observability residual this round. Treat the SLSA models as a coherent nested schema: expose only the aggregate `InTotoStatement` at the root and construct it from validated nested data, rather than flattening eight generic component types or publishing a submodule.

**Tech Stack:** Python 3.14, `ast`, TOML, lazy package facades, Pydantic v2, pytest, Ruff, PolicyOS architecture guardrails.

**Spec:** `architecture/policies/cross_cutting_concerns.toml`; `docs/plans/active/DEBT-REGISTER.md` row `core-security-canonical-interface-contract-drift`; user task contract dated 2026-08-26.

## Global Constraints

- Base is `main` at `238ea72fe`; work stays on attached branch `codex/cross-cutting-contract-drift`.
- No push, merge, rebase, history rewrite, full pytest, or edits to the parallel import-relocation task's files.
- Never edit `src/polisyos/fabric/_adapters/observability.py`; it remains outside every rewrite set.
- Do not edit `architecture/imports/policy.toml`, `architecture/packages/boundaries.toml`, the twelve import-relocation rows, `src/polisyos/pdc/__init__.py`, `src/polisyos/runtime/quality/generation_cycle.py`, or `src/polisyos/runtime/quality/data_state_substrate.py`.
- Public contract additions are exactly `polisyos.common.config`, `polisyos.core.security`, and `polisyos.core.trace`; do not add `polisyos.core.observability` this round and do not publish any security submodule.
- The deep-import baseline may change only by the independently derived 52-edge shrink caused by those three newly supported entrypoints (security 47, trace 4, config 1); zero added edges are admissible.
- Every set-level count comes from two whole-population derivations with path and file-type denominators; disagreement is reported, not normalized away.
- Verification is blast-radius tests, recomputed writers/checkers, Ruff, and the three separately reported repository predicates.

## Pattern Pass

- `P31` / `P40`: security is one member of a four-interface class. Close three members through one contract/import invariant and register the bounded observability residual rather than patching only security.
- `P03` / `P06`: the canonical homes exist, but the exhaustive surface manifest and consumers do not expose/use them consistently. Record only the ratified facades, never their implementation submodules.
- `P04` / `P09`: a registered observability deferral is valid only while its debt status is actively `open`, `open_unmerged`, or `blocked`; `closed` and `folded` cannot authorize a missing supported entrypoint.
- `P29` / `P38`: tests parse the live TOML and full source AST. They do not grep marker strings or equate a generic guardrail exit with this cross-contract property.
- `P35`: the complete tracked denominator at `238ea72fe` is `policy-engine/src/` with 2,789 blobs, including 2,579 `.py` files. Two independent AST visitors agree on all 408 imported-name rows (`sha256:cacfb1fd5abc9bac02464bdd940559d4c5f4a0182ce73abef8be2425ddc224be`).
- `P35` finding: the inherited security ratio `64/83` mixes denominators. The 45 deep statements contain 86 imported-name occurrences (`64` facade-covered, `22` uncovered) and 53 unique names (`34` covered, `19` uncovered). `80 -> 99` is only the hypothetical flatten-all count, not the selected design.
- `P35` review correction: observability truthfulness is 12 statements over 10 unique names—11 Foundry plus 1 IR—not an 11-statement whole-family bucket.
- `P41`: baseline predicates are measured separately at the slice base. The changed source paths are inside all three scanners' source denominators, so post-change parity must be demonstrated by exact count/content comparison, not asserted disjoint.
- Capability state before work: `contract_only`, `surface_missing`, `bridge_missing`, and `semantic_test_missing`. Acceptance signal: supported facade entries resolve in the generated inventory, all selected cross-package imports are exact-facade imports, targeted consumers pass, the register checker re-renders deterministically, and the three inherited predicates retain their separate standings.

---

### Task 1: Add live cross-contract and facade-resolution tests

**Files:**
- Modify: `tests/repo_quality/architecture/test_last_mile_cross_cutting_concerns.py`
- Create: `tests/unit/core/security/test_facade.py`

**Interfaces:**
- Consumes: `architecture/policies/cross_cutting_concerns.toml`, `architecture/public_surface/contract.toml`, and every `src/polisyos/**/*.py` import statement.
- Produces: executable semantic nodes for the three closed interfaces and lazy-resolution checks for ten new security root names.

- [x] **Step 1: Add the cross-contract failing checks**

  Parse the live concern and public-surface contracts. Derive the unique `public_status = "public"` canonical interfaces, declare only `polisyos.core.observability` as the bounded residual tied to `core-observability-canonical-interface-contract-drift`, and assert every other interface is supported. Walk the full source AST and assert every cross-package import of a non-deferred interface targets the exact facade rather than a submodule.

  The exact nodes are:

  ```text
  tests/repo_quality/architecture/test_last_mile_cross_cutting_concerns.py::test_phase1_5_public_canonical_interfaces_are_supported_or_registered_deferred
  tests/repo_quality/architecture/test_last_mile_cross_cutting_concerns.py::test_phase1_5_closed_public_canonical_interfaces_use_exact_facades
  ```

- [x] **Step 2: Add the security facade failing check**

  Parameterize identity checks for these root exports and canonical sources:

  ```python
  EXPECTED_EXPORTS = {
      "AuditLog": "polisyos.core.security.audit_protocol",
      "validate_tenant_id": "polisyos.core.security.db_backend",
      "InTotoStatement": "polisyos.core.security.slsa.models",
      "NamespacedArtifactStore": "polisyos.core.security.namespace",
      "SECURITY_ASSURANCE_REPORT_REF_KEY": "polisyos.core.security.quality_gates",
      "SECURITY_REPORT_FILE": "polisyos.core.security.quality_gates",
      "build_security_assurance_report": "polisyos.core.security.quality_gates",
      "security_gates_from_report": "polisyos.core.security.quality_gates",
      "TenantQuotaRegistry": "polisyos.core.security.quota_registry",
      "TenantQuotaLimits": "polisyos.core.security.tenant_quota",
  }
  ```

  Also assert `_validate_tenant_id` is not exported.

- [x] **Step 3: Run the exact nodes and verify RED**

  Run the two new cross-contract nodes and the new security facade test file. Expected failures are the three absent supported entrypoints, the 45 security plus three trace deep statements, and the ten absent security root exports. A collection error or zero selected tests is not an admissible red receipt.

### Task 2: Reconcile the public manifest and canonical facades

**Files:**
- Modify: `architecture/packages/common.toml`
- Modify: `architecture/packages/core.toml`
- Modify: `architecture/public_surface/contract.toml`
- Modify: `src/polisyos/core/security/__init__.py`
- Modify: `src/polisyos/core/security/db_backend.py`

**Interfaces:**
- Consumes: the ratified `canonical_interface_plus_package_adapters` decisions.
- Produces: three supported entrypoints and a lazy security facade with 90 exports: the existing 80, nine straightforward exports, and aggregate `InTotoStatement`.

- [x] **Step 1: Register only the three approved facades**

  Add `polisyos.common.config` to the `polisyos.common` primary contract and aggregate row. Add `polisyos.core.security` plus `polisyos.core.trace` to the `polisyos.core` primary contract and aggregate row, retaining the pre-existing `polisyos.core.contracts` entry. Preserve each file's schema and surgical formatting.

- [x] **Step 2: Extend the lazy security facade**

  Add all ten mappings above to `_EXPORTS`, their `TYPE_CHECKING` imports, and `__all__`. Keep `_EXPORTS` and `__all__` equal; do not expose `_validate_tenant_id` or the other eight SLSA component models. Give newly public `validate_tenant_id` a Google-style defining docstring.

- [x] **Step 3: Run the security facade tests**

  Expected: all ten identities resolve to the canonical defining objects, and the private alias remains unavailable.

### Task 3: Re-spell all eligible consumers

**Files:**
- Modify security consumers: `src/polisyos/fabric/{io/db.py,security/access_control.py,storage/duckdb_adapter.py,storage/tenant_cas.py,world/query.py}`, `src/polisyos/runtime/http/{authz_middleware.py,cell_router_middleware.py,dependencies.py,dev_identity_middleware.py,errors.py,jwt_auth_middleware.py,routes/auth.py,routes/review.py,security.py,services/control/nl_pipeline.py,services/control/run_lifecycle.py}`, `src/polisyos/runtime/quality/scorecard.py`, `src/polisyos/scientist/{adapters/foundry_bridge.py,methods/search/transfer_context.py,orchestration/engine/context.py,orchestration/workflows/builder.py}`, and `src/polisyos/foundry/methods/equivalence/store.py`.
- Modify trace consumers: `src/polisyos/runtime/http/services/{adapters/core_run.py,debug.py,timeline.py}`.
- Leave already-exact consumers unchanged: `src/polisyos/fabric/security/adapters.py`, `src/polisyos/scientist/orchestration/engine/checkpoint.py`, `src/polisyos/scientist/governance/telemetry.py`, and `src/polisyos/foundry/methods/backends/runtime_fingerprint.py`.

**Interfaces:**
- Consumes: the root facades from Task 2.
- Produces: all 45 original deep security statements routed through the exact facade, 4/4 exact trace statements, and the already-exact config statement; Ruff may consolidate adjacent exact security statements, but no deep statement remains and no observability import is touched.

- [x] **Step 1: Re-spell 43 ordinary security statements**

  Preserve imported names and aliases while changing the source to `polisyos.core.security`.

- [x] **Step 2: Replace the private tenant validator**

  In `fabric/storage/duckdb_adapter.py`, import and call `validate_tenant_id`. The old private alias is the same function object today, so signature, exception translation, and fail-closed behavior remain identical.

- [x] **Step 3: Resolve the SLSA carve-out without flattening nine names**

  Import only `InTotoStatement` from the security root. Build the same strict nested statement through `InTotoStatement.model_validate({...})`; preserve aliases `buildDefinition` and `runDetails`, defaults, datetimes, digests, and serialized bytes. The existing attested-equivalence test is the behavior characterization.

- [x] **Step 4: Re-spell the three trace statements**

  Import `TraceRecord` and `RunTerminality` from `polisyos.core.trace`; do not change the already-exact Scientist consumer.

- [x] **Step 5: Run focused consumer checks and the AST contract nodes**

  Run tenant validation/storage access-control tests, equivalence attestation persistence, trace consumer tests, and both repository-quality nodes. Expected: the selected closed-interface deep-import census is empty.

### Task 4: Regenerate exhaustive public-surface companions

**Files:**
- Modify by canonical writer: `architecture/public_surface/inventory.json`
- Modify by canonical writer: `architecture/baselines/imports/deep_import.json`
- Modify by canonical writer: `docs/reference/public-surface.md`

**Interfaces:**
- Consumes: the manifest and live facade `__all__` values.
- Produces: deterministic inventory/reference projections with 32 supported entrypoints and the security facade's selected 90-name API.

- [x] **Step 1: Run the canonical writer**

  Run `uv run polisyos-tools architecture guardrails sync`. Accept only the measured 3,631 -> 3,579 deep-import baseline shrink: 52 removed entries and zero additions.

- [x] **Step 2: Run inventory checks**

  Run the supported-entrypoint inventory nodes and `uv run polisyos-tools architecture guardrails check`. Corrupt-field drift is covered by the existing public-inventory falsifier test.

### Task 5: Register the full class and regenerate the ledger

**Files:**
- Modify: `docs/plans/active/DEBT-REGISTER.md`
- Modify by canonical writer: `docs/plans/active/LEDGER.md`
- Modify mandatory denominator pins: `tools/quality/validation/check_debt_ledger.py`
- Modify mandatory denominator tests: `tests/repo_quality/tools/test_debt_ledger_checker.py`

**Interfaces:**
- Consumes: executed test identities, final AST receipts, and the debt lifecycle rule that newly registered branch-local work remains `open_unmerged` until merged to `main`.
- Produces: class-member rows for security, trace, config, and observability; deterministic ledger projection.

- [x] **Step 1: Reword security and add three missing rows**

  Keep the pre-existing security row `open`; mark the three rows first registered on this branch `open_unmerged`. Reword security as a member of the class and append the denominator correction plus carve-out rulings. Add trace/config rows with the executed green nodes. Add observability with its 252-statement/220-file sizing, an executable AST zero predicate, and a scoped multi-task proposal.

- [x] **Step 2: Execute every closure signal before recording it**

  Run each named pytest selector with nonzero collection, then its body. Record the two independent full-tree AST derivations of observability's current 185 deep statements as the open-state receipt; while the debt is actively deferred, the exact-facade selector deliberately excludes observability and serves as the executable future closure signal.

- [x] **Step 3: Recompute denominator pins and regenerate**

  Derive register totals twice, update only the measured constants/assertions, run `check_debt_ledger.py --write`, then `--check` and the targeted checker tests.

### Task 6: Closeout verification and review

**Files:**
- Verify every changed mechanism and mandatory companion; never include `src/polisyos/fabric/_adapters/observability.py` in the diff.

**Interfaces:**
- Consumes: integrated branch state.
- Produces: fresh command/exit/count receipts and an independent review.

- [x] **Step 1: Run Ruff and targeted tests**

  Run `.venv/bin/python -m ruff check` over changed Python files and the targeted pytest nodes only. No full pytest.

- [x] **Step 2: Re-run the three predicates separately**

  Measure uptime before/after and `/usr/bin/time -p` user/sys for: plain import linter (expected exit 1 / 88), release guardrail (expected exit 0 / zero creep), and fail-closed package-import gate (expected exit 1 / 143 findings). Any movement is a finding.

- [x] **Step 3: Independent review and branch readback**

  Review the complete diff against this plan and the user's exclusions. Confirm attached branch, clean tree, exact commits, and re-read every delivered path from the branch before hand-back.
