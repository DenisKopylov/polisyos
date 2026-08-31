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

---

## Round 2 — execute the ruled migrations

**Round-2 goal:** Remove the live Scientist -> Runtime counter-direction, make the
Fabric world facade one exact public entrypoint for both import predicates, complete all
already-ruled observability re-spellings, consolidate changed-file discovery on one
fail-closed Git-root owner, and close or concretely block every row.

**Approved architecture:** Preserve Runtime -> Scientist as the only direction. Shared
contracts needed by Scientist move to an existing lower/Scientist owner, and Runtime
consumes that owner; no exception or linter-only export substitutes for relocation.
Exact facade membership comes from the aggregate and primary public-surface contracts,
which the release collector already consumes. Changed-file identity is a worktree-rooted
absolute path returned by `tools.lib.cache.git_changed_files`; both the import linter and
schema generator consume that one owner and treat an indeterminate Git command as an
error, never an empty change set.

### Round-2 pattern pass

- Relevant patterns: P03, P06, P27, P28, P29, P31, P33, P35, P37, P38, P40, P41.
- Existing defects: the ruled reverse edge is still executable; exact Fabric facade
  membership is absent from the contract read by the release collector; the import
  linter duplicates a stricter Git implementation beside a permissive shared owner; and
  the observability facade omits already-ruled exports while consumers import their
  implementation modules.
- Target pattern: owner-side contract relocation with the superseded Runtime-owned
  imports removed; one exact facade contract with a negative descendant probe; one
  shared Git-root resolver with two consumer-level regressions; canonical AST rows and
  branch path sets for every count.
- Capability states before execution: Scientist/Runtime
  `implemented_but_not_orchestrated`; Fabric `surface_missing`; observability
  `surface_missing` with an institutionally supplied adjudication prerequisite; shared
  Git change discovery `verification_missing`; Runtime/Corpus `absent/unallocated` only
  for the package-owner appointment.
- Acceptance signal: focused behavior tests first fail on the current defects, then pass;
  the complete Scientist corpus has zero Runtime imports and the matrix has no
  Scientist -> Runtime allowance; Fabric exact-facade imports pass both predicates while
  descendants remain rejected; non-truthfulness observability deep imports are zero;
  both changed-only consumers resolve nested-product paths exactly once and fail closed;
  six peer-branch changed-path scans record rule-specific outcomes.

### Task 7: Pin the round-2 predicates in failing tests

**Files:**
- Modify: `tests/repo_quality/architecture/test_import_governance_contract.py`
- Modify: `tests/repo_quality/tools/test_phase5_tooling.py`
- Modify only where the existing public-surface contract tests require it:
  `tests/repo_quality/architecture/test_last_mile_cross_cutting_concerns.py`

1. Add a complete AST assertion that Scientist has no absolute Runtime import and the
   direction matrix no longer admits Runtime from Scientist.
2. Add a behavioral public-surface assertion that `polisyos.fabric.world` is exact and a
   `polisyos.fabric.world.store` descendant remains deep/forbidden.
3. Add real nested-worktree changed-file tests for the shared helper, import linter, and
   schema generator; include invalid base, diff failure, untracked failure, and command
   launch failure paths with exact diagnostics.
4. Run only the new exact nodes and record the intended red conditions before production
   edits.

### Task 8: Execute the Scientist -> Runtime migration

**Files:** the eleven measured Scientist consumers, the smallest existing shared or
Scientist owners required by their imported contracts, direct Runtime consumers of any
relocated owner, `architecture/imports/policy.toml`, and focused mirrored tests.

1. Reproduce and persist the pre-change canon over 584 Scientist and 280 Runtime Python
   files before moving a statement.
2. Classify each of the 13 statements by symbol owner. Re-exporting from an arbitrary
   facade is not relocation: definitions move only when their semantic owner moves, and
   Runtime imports the retained owner.
3. Preserve object identity/serialization for public DTOs and replay records; run direct
   consumer tests after each coherent owner group.
4. Require a post-change complete Scientist AST census of zero Runtime statements before
   deleting `runtime` from `internal.allow.scientist`. Run the real import gate and prove
   the mutual declaration has disappeared without exception cover.

### Task 9: Ratify the exact Fabric world facade in enforcement

**Files:**
- Modify: `architecture/public_surface/contract.toml`
- Modify: `architecture/packages/fabric.toml`
- Modify only if the exact consumer needs an already-existing curated symbol:
  `src/polisyos/fabric/world/__init__.py`
- Regenerate the public-surface inventory/reference through the repository guardrail.

1. Add exactly `polisyos.fabric.world` to both public-surface owners; do not add store or
   materialize descendants.
2. Verify the existing four-symbol Runtime consumer imports only curated facade exports.
   Do not export `create_world_snapshot` and do not delete the Phase-0 witness.
3. Exercise ARCH004 and `collect_deep_import_edges()` on the same exact edge and on a
   descendant negative control; require agreement.

### Task 10: Complete the ruled observability mechanics

**Files:** `src/polisyos/core/observability/__init__.py`, the 173 measured non-truthfulness
consumers, and focused import/facade tests. Keep
`src/polisyos/fabric/_adapters/observability.py` untouched.

1. Promote the three determinism names and `is_hpc_observability_enabled` through the
   exact Core observability facade with optional-dependency behavior preserved.
2. Re-spell 166 determinism, two HPC-config, two pricing, and three propagation statements
   to the exact facade. Use an AST-derived file set and a syntax-aware mechanical rewrite;
   do not execute the truthfulness family.
3. Re-run the complete 2,611-file canon. Require the only remaining cross-package deep
   imports beneath Core observability to be the ten truthfulness names in eleven
   statements. Keep the deferred interface and final contract/inventory reconciliation
   in place until that owner adjudication lands; type the row `blocked` on that concrete
   decision.

### Task 11: Consolidate changed-file discovery

**Files:**
- Modify: `tools/lib/cache.py`
- Modify: `tools/quality/lint/lint_imports.py`
- Modify: `tools/quality/diagnostics/gen_schema.py`
- Modify: `tests/repo_quality/tools/test_phase5_tooling.py`

1. Make the shared helper derive `git rev-parse --show-toplevel`, verify the base as a
   commit, resolve diff and untracked names exactly once against that root, and surface
   launch/root/base/diff/untracked failures with stable diagnostics.
2. Preserve pathspec semantics relative to the caller's supplied product root while Git
   executes at the worktree root.
3. Replace the linter duplicate with the shared owner and route schema generation through
   the same failure semantics. A changed-only consumer converts helper failure to its
   existing exit-2/error boundary; an empty set means a proved empty set only.
4. Demonstrate red/green/revert sensitivity for both consumers using nested worktree
   fixtures.

### Task 12: Cross-lane compatibility and closeout

1. For lanes A, B, C, D, E, and G, enumerate every changed Python path against base
   `784d02014` from its attached worktree. Run this branch's final v2 policy and linter
   implementation against that lane's sources in changed-only mode; record ARCH007,
   policy-version, and root-coverage outcomes separately.
2. Freeze source, run only exact nodes plus direct importer/contract blast radius, Ruff on
   changed Python, import guardrails, the bound debt-ledger parity check, and docs
   lifecycle parity. Compare blocker identity sets, not just exit codes.
3. Re-read the failure register, run independent delta review and verification, and
   append a seven-block supersession dossier. Every verdict is `closed` or `blocked`;
   every block names its rerunnable predicate, exit code, measured canon, and exact
   register prose.
