# GY-N10a Provenance Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make N7 timing truthful and operational, source identity portable, and all free-grow gap witnesses seam-bound without changing engine modules.

**Architecture:** The checker will split N7's stable owner-content projection from the time-bearing engine receipt retained in excluded runtime metadata. A generic AST seam-witness helper will resolve and hash a specific function segment using a repo-relative path, then validate every emitted gap fail-closed.

**Tech Stack:** Python 3.14, existing Pydantic N7 contracts, AST, JSON content hashes, pytest, Ruff.

## Global Constraints

- Change no file below `src/polisyos/`.
- Do not alter census SQL, domain ranking, pack entry selection, or N6 smoke inputs/terminal behavior.
- Operational timestamps and wall time must be excluded from every pack content hash.
- Use one generic gap-witness path for all seven gaps; missing symbols must emit `gap_witness_target_missing`.
- Run only focused validator, focused pytest, and Ruff checks.

---

### Task 1: Add failing behavioral tests

**Files:**
- Modify: `tests/unit/runtime/quality/test_second_domain_pack.py`

- [ ] Add a two-clock N7 test proving actual capture metadata changes while the
  content-bound N7 receipt and manifest hash do not.
- [ ] Add a source-hash equivalence test for canonical and `../` paths.
- [ ] Add all-gap seam-witness coverage and a missing-symbol mutation that
  expects `gap_witness_target_missing`.
- [ ] Run the new focused tests and observe the current failures.

### Task 2: Repair checker-only provenance and witnesses

**Files:**
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`

- [ ] Move the full N7 engine receipt into excluded operational metadata and
  create a stable owner-content projection/hash.
- [ ] Make source identity repo-relative and content-only.
- [ ] Build, validate, and corrupt-test generic function-segment witnesses for
  all seven gaps, binding N5 to `_build_boundary_world_model_record`.
- [ ] Run the focused tests to green.

### Task 3: Regenerate and verify

**Files:**
- Modify: `architecture/policy_design_case/layer3_gy_second_domain_census.json`
- Modify: `architecture/policy_design_case/layer3_gy_second_domain_pack.json`
- Modify: `architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json`
- Modify: `architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json`

- [ ] Regenerate with `--write` and verify content stability on a second write.
- [ ] Run the required check, mutation, rederive, focused tests, Ruff, and
  zero-engine diff checks.
- [ ] Commit the scoped repair after independent review.
