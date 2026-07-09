# GY-N10a Second-Domain Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible, owner-derived education-domain substrate pack and report every current free-grow seam without changing engine modules.

**Architecture:** A single validator/builder reads existing L1/L2/S0/N7/N6 owners and emits content-addressed artifacts. It retains one real journal-first N7 receipt as failure evidence without granting its projected registration authority, models unavailable durable lever/writability intake as typed gaps, then proves that the strict DesignProblem reaches a real N6 typed terminal through the grammar-fallback path.

**Tech Stack:** Python 3.14, DuckDB read-only queries, existing Pydantic runtime contracts, JSON canonicalization, pytest, Ruff.

## Global Constraints

- Change no file below `src/polisyos/`.
- Every committed pack fact must be reconstructed from an owner query, owner build, or N6 run.
- Do not create a registry format; manifest-only joins are permitted.
- Keep owner queries parameterized and single-pass; exclude operational timing metadata from content hashes and preserve it across byte-stable rewrites.
- Treat L2/L3 -> durable S0/L6 persistence and default N4/N5 consumption gaps as blocks, never as data fixtures.
- Run only the user-specified scoped checks; mutation mode intentionally exits 1.

---

### Task 1: Establish the generated artifact family and plan record

**Files:**
- Create: `docs/superpowers/specs/2026-07-09-second-domain-pack-design.md`
- Create: `docs/superpowers/plans/2026-07-09-second-domain-pack.md`
- Modify: `architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json`

**Interfaces:**
- Consumes: the existing GY-N0 ledger task/mapping shape.
- Produces: a `GY-N10a` data-only ledger record referencing existing owner IDs.

- [x] Record the owner-first design and failure-pattern pass.
- [x] Add `tasks["GY-N10a"]` and a mapping to existing S0/N7/L6/N6 owners, without creating a new owner row.
- [x] Verify the ledger validator accepts the extra task key.
- [x] Commit the planning documents before implementation changes.

### Task 2: Write owner-rederive tests before the builder

**Files:**
- Create: `tests/unit/runtime/quality/test_second_domain_pack.py`
- Create: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`

**Interfaces:**
- Consumes: L1 `ds_observations`, L2 `ac_causal_claims`/`ac_parameter_estimates`/`ac_skg_*`, S0 registry builder, `GenerationCycleController`.
- Produces: `build_live_bundle(repo_root)`, `validate_frozen_bundle(repo_root)`, and mutation reports.

- [x] Add a failing test that rederives owner query hashes and rejects a manually appended well-shaped entry with `pack_entry_not_owner_derived`.
- [x] Add a failing test that injects first-vertical outcome/covariate/lever values and expects a computed distinctness failure.
- [x] Add a failing test that marks a crash/mismatch trace as pass and expects `smoke_terminal_not_honest`.
- [x] Run the focused tests and observe the missing-builder failure.

### Task 3: Build the census and owner-derived pack

**Files:**
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
- Create: `architecture/policy_design_case/layer3_gy_second_domain_census.json`
- Create: `architecture/policy_design_case/layer3_gy_second_domain_pack.json`
- Create: `architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json`

**Interfaces:**
- `build_live_bundle(repo_root: Path) -> dict[str, dict[str, object]]`
- `write(repo_root: Path) -> None`
- `rederive_audit(repo_root: Path) -> dict[str, object]`

- [x] Query the three candidate domains with one parameterized L1 aggregate and direct L2 exact-prefix coverage queries.
- [x] Score eligible candidates from normalized measured coverage, grounding, S0/L6/CG3 feasibility, non-panel shape, transport measurement, and computed distinctness; select education.
- [x] Rebuild pack outcomes, covariates, candidate levers, L2 grounding coverage, and S0 build evidence from the owners.
- [x] Run one real journal-first N7 attempt and reject its no-result/synthetic registration path from pack authority.
- [x] Emit only typed gaps for non-persistent N7/CG3/S0/L6 and N4/N5 seams.
- [x] Run the tests to turn green.

### Task 4: Capture strict N6 cycle-entry evidence

**Files:**
- Create: `architecture/policy_design_case/layer3_gy_second_domain_smoke_design_problem.json`
- Create: `architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json`
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`

**Interfaces:**
- Consumes: owner-derived education candidate levers and `GenerationCycleController.run`.
- Produces: strict DesignProblem JSON and `GenerationCycleRun.model_dump(mode="json")` trace.

- [x] Build the lever IDs and unbound target-slot candidates from L2 source/effect rows, never from a hand list.
- [x] Execute the real N6 controller with its grammar fallback, preserving the unavailable N4 owner status.
- [x] Record the typed `a_spec_gap`/`cgf_disposition_missing` terminal and the separate N6 single-terminal validation gap.
- [x] Reject synthetic crash or first-vertical mismatch traces in the validator tests.

### Task 5: Register, freeze, and verify the artifact family

**Files:**
- Modify: `architecture/generated_artifacts.toml`
- Modify: `docs/reference/generated-artifacts.md`
- Modify: `architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json`
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`

**Interfaces:**
- `declared_outputs() -> list[str]` names every frozen artifact.
- CLI supports `--check`, `--write`, `--rederive-audit`, and `--corrupt-field-drift-check`.

- [x] Register the generated/committed lifecycle family and synchronize the reference documentation.
- [x] Make `--check` frozen-only and cheap; make `--rederive-audit` run owners and N6.
- [x] Make mutation mode detect hand-authored provenance, distinctness smuggling, smoke dishonesty, and engine-diff scope violations.
- [ ] Run the scoped commands, inspect their exit codes, commit the data/artifact/validator/test scope, and re-run the durable no-engine-diff check from the recorded base revision.
