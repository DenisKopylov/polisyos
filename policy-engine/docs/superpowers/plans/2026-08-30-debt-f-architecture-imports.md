# Debt F Architecture And Imports Implementation Plan

> **For Codex:** Execute this plan in the existing `codex/debt-f-architecture-imports`
> worktree. Preserve the ratified zero-exception result. Do not modify the debt
> register or Atlas surfaces.

**Goal:** Make the import direction matrix and package ownership/narrowing register
enforce one canonical edge definition, close the owned coverage defects, remove the
DS18 counter-edge at its owner, and produce evidence-backed dispositions for all seven
register rows.

**Architecture:** `architecture/imports/policy.toml` remains the enforced root-direction
matrix. It names `architecture/packages/boundaries.toml` as the ownership and narrowing
register; `lint_imports.py` loads that register, validates its real-root coverage, and
applies strict submodule narrowings only after the root direction is allowed. A canonical
edge is `(source root, target root, normalized absolute target module)`; a narrowing is
the sorted set of admitted absolute target prefixes for one allowed root pair. Counts are
derived from sorted AST rows over `Path.rglob("*.py")`, including root-level files.

**Tech Stack:** Python 3.11+, stdlib `ast`/`tomllib`, pytest, TOML contracts.

---

## Pattern pass

- Relevant patterns: P06, P13, P27, P29, P31, P33, P35, P37, P38, P40, P41.
- Existing defects: two files state overlapping import authority without a shared
  classifier; the direction matrix contains five nonexistent roots; seven real roots
  have no package-governance disposition; one package contract names a nonexistent
  guard; the cycle collector counts a deferred incident bridge as a static SCC; two
  inherited corpus denominators are stale or noncanonical.
- Target pattern: one load path from direction matrix to ownership/narrowing register;
  complete strict-root coverage with explicit ungoverned reasons; negative tests against
  sibling submodules and missing governance; owner-side edge removal; canonical sorted
  tuples rather than count inequality.
- Capability state before work: import authority `verification_missing`; package coverage
  `producer_missing`/`verification_missing`; Scientist/Runtime `implemented_but_not_orchestrated`
  for the chosen one-way migration; Fabric `blocked` on shared surface ruling;
  observability `surface_missing`/`verification_missing`; Runtime/Corpus `blocked` on a
  Corpus owner; DS18 `verification_missing` for the static counter-edge repair.
- Acceptance signal: exact targeted tests and gates below, plus a seven-row closure
  dossier with command, exit code, canonical measure, and append-only register prose.

## Task 1: Pin the authority roles and strict-root coverage in failing tests

**Files:**
- Create: `tests/repo_quality/architecture/test_import_governance_contract.py`
- Modify: `tests/repo_quality/tools/test_lint_imports_phase3.py`

1. Add a repository contract test that requires the exact role declarations, a real
   package-boundary path, zero known/allowed roots without directories, and complete
   real-root coverage by either `[[package]]` with a `team-*` owner or an explicit
   nonblank deliberately-ungoverned reason.
2. Add behavioral linter tests proving an admitted narrow prefix passes while a sibling
   submodule under the same allowed root fails with `ARCH007`.
3. Add falsifiers for a missing governed-root disposition and a nonexistent matrix root.
4. Run only the new exact nodes and confirm red for the intended missing behavior.

## Task 2: Execute the settled import-authority and package-coverage rulings

**Files:**
- Modify: `architecture/imports/policy.toml`
- Modify: `architecture/packages/boundaries.toml`
- Modify: `tools/quality/lint/lint_imports.py`

1. Declare `policy.toml` the `enforced_direction_matrix` and point it at the package
   ownership/narrowing register.
2. Remove `academic`, `batch_common`, `batch_snapshot`, `datasets`, and `ukraine_data`
   from both the known-root denominator and `[internal.allow]`.
3. Declare `boundaries.toml` the `ownership_and_narrowing_register`, replace the stale
   nonexistent guard claim with the actual readers, and record the seven real uncovered
   roots as deliberately ungoverned with specific reasons. Keep Corpus owner unappointed.
4. Extend `read_policy()` to validate version-2 role, path, directory, and coverage
   invariants; derive strict narrowings from exact-root package entries; include the
   boundary contract in changed-scan sentinels and cache fingerprints.
5. Enforce the derived narrowing after root-direction admission. Diagnostic:
   `[ARCH007] forbidden narrowed internal import: {source_root} -> {target_root} via
   {target_module} (allowed_prefixes={...})`.
6. Run the exact red tests, the repository import gate, and a mutation witness that keeps
   the root direction but substitutes `polisyos.data_forge.kernel`; require failure.

## Task 3: Rule the Scientist/Runtime direction from a complete AST census

**Files:**
- Modify: `docs/superpowers/journals/2026-08-30-debt-f-architecture-imports.md`

1. Walk all Scientist and Runtime Python files with `Path.rglob("*.py")`; canonicalize
   each statement as sorted JSON `(path, line, normalized target, ordered aliases, scope)`.
2. Record both file denominators, statement/alias/file measures, and hashes. Explicitly
   reconcile the inherited 276 Runtime proxy with the complete 280-file corpus.
3. Rule the one-way target as Runtime consuming Scientist because the complete measured
   edge is 74 statements versus 13 in reverse. Keep the row open until the 13 reverse
   statements are relocated; do not remove the permission while live imports remain.

## Task 4: Remove the DS18 incident/monitors counter-edge at its owner

**Files:**
- Modify: `src/polisyos/scientist/governance/continuous/incident.py`
- Modify: `src/polisyos/scientist/governance/continuous/monitors.py`
- Modify: `tests/repo_quality/architecture/test_import_governance_contract.py`

1. Add a failing test against the real import-graph collector requiring no SCC containing
   both modules and preserving the module-level `incident -> monitors` edge.
2. Move the incident-specific persistence bridge into `incident.py`; do not change its
   artifact verification semantics or add a compatibility counter-import.
3. Compare canonical SCC sets before and after. Require exactly the incident/monitors SCC
   to be removed and no SCC to be added.

## Task 5: Record bounded decisions for the three non-owned implementations

**Files:**
- Modify: `docs/superpowers/journals/2026-08-30-debt-f-architecture-imports.md`

1. Fabric: record `blocked`; the exact `polisyos.fabric.world` facade must be added by the
   public-surface owner and both ARCH004 and the release collector must derive from it.
   Preserve the Phase-0 witness and do not export `create_world_snapshot`.
2. Observability: keep `open`; rule determinism root promotion/re-spelling and the isolated
   HPC-helper root promotion. Leave truthfulness to IR/Core owner adjudication and leave
   already-covered propagation/pricing as an unexecuted mechanical re-spelling. Do not
   touch `fabric/_adapters/observability.py`.
3. Runtime/Corpus: rule Runtime -> Corpus forbidden and the fixture validator owned by
   tools/tests; record `blocked` on the absent Corpus package owner, without adding an
   exception or weakening the direction matrix.

## Task 6: Targeted verification, review, commits, and dossier

**Files:**
- Modify: `docs/superpowers/journals/2026-08-30-debt-f-architecture-imports.md`

1. Run exact pytest nodes for changed behavior and their direct importer tests only.
2. Run `lint_imports.py`, the package gate’s focused mode, Ruff on changed Python files,
   and architecture guardrails if its bound environment is available.
3. Run the two required before/after checks: debt ledger `--check` exit 0 under the bound
   interpreter, and docs lifecycle with exactly six measured findings.
4. Run a delta review against this plan; bucket findings under P40 and repair only owned
   blocking defects.
5. End the journal with seven dossier blocks, arithmetic split core/adjacent, the two
   canonical census reproductions, every tightened rule/diagnostic, observability decisions,
   and named out-of-scope findings.
6. Before every commit, verify `git status -sb` names
   `codex/debt-f-architecture-imports`; commit at each coherent clean boundary.
