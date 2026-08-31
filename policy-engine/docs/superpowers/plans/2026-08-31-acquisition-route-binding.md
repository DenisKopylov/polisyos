# Acquisition Route Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind one current, data-shaped acquisition route to a canonical World Bank WDI authority
entry, one fresh provisioned attempt, bounded constraints, and server-governed evidence storage.

**Architecture:** Extend the existing N13b executor with a strict, content-bound route-binding DTO
and resolver. Implement the existing `AcquisitionExecutionPort` with a production class that leases
one authority-provisioned attempt, derives route-scoped storage under the runtime root, invokes the
real executor, and returns the existing quarantined owner result. Keep the HTTP schema stable and
state the one-family limit through the existing `external_nonclosures` surface.

**Tech Stack:** Python 3.14, Pydantic v2, pytest, PolicyOS canonical acquisition authority,
append-only Fabric journal, filesystem CAS.

**Spec:** `docs/superpowers/journals/2026-08-31-debt-j-acquisition-route-binding.md`

## Global Constraints

- World-Bank-WDI-only; every other connector family is explicitly `surface_out_of_scope`.
- No caller-supplied `entry_id`, `attempt_id`, `journal_path`, `cas_root`, or execution constraint.
- Missing, ambiguous, stale, cross-scope, replayed, or owner-drifted inputs fail before connector use.
- Preserve the `producer_missing` fail-closed behavior when a real authority/provider is absent.
- Do not modify schema/client/OpenAPI/dashboard, task A, task I, or task D paths.
- Run only focused acquisition checks; one heavy verifier at a time.

---

### Task 1: Content-bound route-to-authority resolver

**Files:**
- Modify: `src/polisyos/runtime/quality/acquisition_executor.py`
- Test: `tests/unit/runtime/quality/test_live_acquisition_executor.py`

**Interfaces:**
- Consumes: `VerifiedAcquisitionRouteClosure`, `CanonicalAcquisitionAuthority`,
  `AcquisitionAuthorityRegistry`, and `AcquisitionAuthorityProvision`.
- Produces: `WorldBankWDIRouteExecutionBinding` and
  `resolve_world_bank_wdi_route_execution_bindings(...)`.

- [ ] Add a failing positive test whose exact L1 variable demand matches one unique live registry
  entry and assert the literal entry id, provisioned attempt id, ISO-3 country, one-year range and
  fixed operational ceilings.
- [ ] Run that exact node and confirm it fails because the resolver is absent.
- [ ] Implement the strict binding DTO and the smallest resolver that reopens and content-binds the
  registry/provision/entry/harness receipt and calls the existing authority-scope checker.
- [ ] Run the exact node and confirm it passes.
- [ ] Add table-driven failing cases for missing/ambiguous variable fields, wrong requirement shape,
  unresolved/ambiguous entry, non-World-Bank connector, cross-country/year scope, absent harness
  attempt, and owner content drift; each must fail before a connector observer can run.
- [ ] Run the focused resolver cases and confirm they pass.

### Task 2: Tenant/route-bound production port and freshness lease

**Files:**
- Create: `src/polisyos/runtime/http/services/acquisition_surface_execution.py`
- Modify: `src/polisyos/runtime/http/services/acquisition_action_service.py`
- Test: `tests/integration/core_runtime/test_acquisition_route_execution_binding.py`

**Interfaces:**
- Consumes: Task 1's binding resolver, the existing `execute_live_catalog_acquisition`, the current
  `AcquisitionExecutionPort`, and the server runtime root.
- Produces: `WorldBankWDIAcquisitionExecutionPort` and a production factory that accepts the
  `ControlPlaneService`, not raw journal/CAS paths.

- [ ] Write a failing integration test using the real concrete production class (not `_Port` or
  `_worker_harness`) and a controlled executor seam; assert the complete binding reaches the
  executor once with derived paths beneath the runtime root and returns the existing quarantine
  result.
- [ ] Run the exact node and confirm it fails because the production class is absent.
- [ ] Implement exclusive attempt leasing, scope-hashed storage derivation, executor invocation,
  and fail-closed re-entry methods; return only already-persisted evidence refs.
- [ ] Run the exact node and confirm it passes.
- [ ] Add negative integration cases removing entry authority, fresh attempt, or in-scope
  constraints and assert zero executor/provider calls; add a replay case and a cross-tenant case.
- [ ] Run those exact nodes and confirm they pass.
- [ ] Wire the production factory only for the production execution profile; owner absence leaves
  the service's existing `producer_missing` posture intact.

### Task 3: Existing route surface and result-contract decision

**Files:**
- Modify: `src/polisyos/runtime/http/services/acquisition_action_service.py`
- Test: `tests/integration/core_runtime/test_acquisition_route_execution_binding.py`

**Interfaces:**
- Consumes: the existing `AcquisitionRouteProjection.external_nonclosures` and readiness literals.
- Produces: explicit `connector_families_except_worldbank.wdi:surface_out_of_scope` projection and
  real `execution_capability=ready` only when the production port exists.

- [ ] Add a failing projection test proving the connector-family limit is visible and that absent
  authority or execution ownership remains `producer_missing`.
- [ ] Run the exact node and confirm the missing surface statement fails.
- [ ] Add the World Bank scope limitation through the existing tuple without changing the Pydantic
  field set, response schema, client, or `AcquisitionOwnerExecutionResult`.
- [ ] Run the exact node and confirm it passes.

### Task 4: Verification and append-only closure dossier

**Files:**
- Modify: `docs/superpowers/journals/2026-08-31-debt-j-acquisition-route-binding.md`

**Interfaces:**
- Consumes: the frozen diff and fresh focused verifier outputs.
- Produces: one terminal Register closure block with exact commands, exit codes, remaining E-row
  work, and append-only architect prose.

- [ ] Run focused unit and integration acquisition nodes, then the complete changed test files.
- [ ] Run Ruff on changed Python files and the architecture guardrail once, serially.
- [ ] Run debt-ledger and docs-lifecycle baselines and prove the blocker/finding sets did not grow.
- [ ] Re-open the failure-pattern register, inspect the final diff, verify branch attachment, and
  append a `closed` or concrete `blocked_by` dossier block.
- [ ] Commit the verified implementation and re-read the delivered branch state.
