# Debt F Architecture And Imports Journal

## Session identity

- Worktree: `.worktrees/debt-f-architecture-imports`
- Branch: `codex/debt-f-architecture-imports`
- Base and starting HEAD: `784d020148c56e9bfb3a3631909ba11232210a9f`
- Starting state: attached and clean.
- Forbidden repairs preserved: no witness deletion, exception addition/renewal, facade
  export solely for lint satisfaction, predicate loosening, debt-register edit, or Atlas
  surface edit.

## Evidence journal

### 2026-08-30 — pre-change exploration

- Read all seven register rows, both predecessor plans, contributor instructions, and the
  failure/repair register before planning.
- Strict root census found 30 matrix allow rows, 18 boundary roots, five nonexistent
  matrix roots (`academic`, `batch_common`, `batch_snapshot`, `datasets`, `ukraine_data`),
  and seven real roots without package-governance disposition (`corpus`,
  `data_requirement`, `legal_requirement`, `pdc`, `policy_grammar`, `schemas`,
  `scholar_requirement`).
- Strict narrowing census reproduced five remaining root-pair narrowings: Fabric,
  Foundry, IR, Lex, and Scientist may reach Data Forge only through
  `polisyos.data_forge.read_api`.
- Complete AST census reproduced the supplied edge statement/alias/file counts, but not
  the supplied Runtime file denominator. `Path.rglob("*.py")` finds 584 Scientist files
  and 280 Runtime files. The 276 proxy is `git ls-files 'src/polisyos/runtime/**/*.py'`,
  which omits four root-level files; one omitted file contains five measured statements.
- Fresh observability census finds 251 cross-package statements in 219 files, of which
  184 are deep. The register’s 252/220/185 corpus predates the later IR truthfulness
  relocation and is not the current subject set.

## Verification log

- `uv sync --frozen --extra test --extra lint` — exit 0; the worktree interpreter is
  bound and includes pytest, RDFLib, and Ruff.
- Red phase:
  `pytest -q tests/repo_quality/architecture/test_import_governance_contract.py
  tests/repo_quality/tools/test_lint_imports_phase3.py::{three narrowing nodes}` —
  exit 1 with five intended failures: missing role, five dead roots, no canonical
  narrowing projection, the Incident/Monitors SCC, and no sibling rejection.
- Import-governance green phase:
  `.venv/bin/python -m pytest -q
  tests/repo_quality/architecture/test_import_governance_contract.py
  tests/repo_quality/tools/test_lint_imports_phase3.py
  tests/repo_quality/tools/test_phase5_tooling.py::{three lint-import nodes}` — exit 0,
  17 selected tests passed.
- Projection blast radius:
  `.venv/bin/python -m pytest -q
  tests/repo_quality/architecture/test_import_policy_projection.py` — exit 0,
  11 selected tests passed. The test now pins the complete 25-root denominator and the
  current Scientist -> Runtime live edge rather than a stale Foundry example.
- Import-governance Ruff:
  `.venv/bin/python -m ruff check tools/quality/lint/lint_imports.py
  tests/repo_quality/tools/test_lint_imports_phase3.py
  tests/repo_quality/architecture/test_import_governance_contract.py
  tests/repo_quality/architecture/test_import_policy_projection.py` — exit 0.
- DS18 green phase:
  `.venv/bin/python -m pytest -q
  tests/repo_quality/architecture/test_continuous_incident_import_cycle.py
  tests/unit/scientist/governance/continuous/test_incident.py` — exit 0,
  five selected tests passed.
- DS18 Ruff:
  `.venv/bin/python -m ruff check
  src/polisyos/scientist/governance/continuous/incident.py
  src/polisyos/scientist/governance/continuous/monitors.py
  tests/repo_quality/architecture/test_continuous_incident_import_cycle.py` — exit 0.
- The direct `test_monitors.py` blast-radius selection exits 2 during collection in both
  the task base and the final tree. The stack stops in the pre-existing
  `control_plane_store -> control.api -> run_lifecycle -> control_plane_store` partial
  initialization before reaching this task's changed `monitors.py`; it is an inherited
  collection failure, not green evidence.
- Full-source import linter on base `784d02014` — exit 1 with exactly one violation:
  Runtime -> Corpus at `governed_projection_validation_worker.py:560`, `ARCH001`, plus
  one allowed package-cycle warning. The final-tree run has the same one violation and
  warning; Task F added zero linter violations and zero exception cover.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python
  tools/quality/validation/check_docs_lifecycle.py` — exit 1 with exactly six findings,
  the supplied unchanged baseline: two architect-owned LEDGER metadata findings and four
  stale frontend-path references outside this lane.
- Bound debt-ledger replay on the final tree — exit 1, not the supplied exit-0
  expectation: 18 `closure_signal_identity_unresolvable` blocking findings. The exact
  bound command replayed from base `784d02014` in an isolated Git clone also exits 1 and
  contains the same 18 unresolved identities (plus base-specific closure-commit and
  rendered-ledger drift). None of Task F's changed paths is in those 18 selection inputs.
  Under P41 these 18 are inherited and the supplied exit-0 expectation is stale; this task
  does not modify the architect-only ledger pin or any reported selection.
- The task's literal unbound command,
  `PYTHONPATH=. python3 tools/quality/validation/check_debt_ledger.py --check`, exits 0
  with 32 `closure_signal_collection_host_unknown` informational findings. Per the task's
  own warning, that green degrades blocking checks and is recorded for before/after parity,
  not accepted as verification evidence.
- Post-review targeted wave: `.venv/bin/python -m pytest -q` over the complete
  `test_import_governance_contract.py`, `test_lint_imports_phase3.py`,
  `test_import_policy_projection.py`, `test_continuous_incident_import_cycle.py`, and
  `test_incident.py` files plus eight exact lint-import functions (nine cases) in
  `test_phase5_tooling.py` — exit 0, 53 selected cases passed after adding both
  no-`__init__.py` root shapes, five boundary-version mutations, and the boundary
  sentinel case.
- Real-worktree changed-only replay against base `784d02014` — exit 1 after a forced
  full scan of 2,611 Python files, with the same single Runtime -> Corpus ARCH001 and
  zero exception cover. It no longer returns a false exit-0 skip from a duplicated
  `policy-engine/policy-engine/...` path.
- `.venv/bin/python -m pytest -q
  tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py::test_phase6_1_public_surface_and_package_boundary_dependencies_agree`
  — exit 0; the changed ownership/narrowing register agrees with the current public
  surface dependency projection.
- `uv run polisyos-tools architecture guardrails check --skip-generated-checks` — exit 0.
  The full generated wave is not accepted as evidence: the current tree reaches an
  unrelated trust-posture generated mismatch, while the isolated base replay lacks the
  clone-local venv required by two generators, so same-command provenance is not
  established.
- The exact Phase-6.1 dependency-report node exits 1 with 21 expired-import-exception
  contract errors and no boundary-contract error. Its complete base provenance was not
  replayed, so this remains `not_established`, not an inherited-red claim and not closure
  evidence for this task.
- Final independent delta reviews through commit `4a2334248` — GO with no owned-repair
  finding. Reviewers independently exercised regular, namespace-style, and root-module
  denominator mutations; missing/legacy/future/float/string/boolean boundary versions;
  nested-worktree boundary sentinels; persisted-baseline invalidation; the DS18
  counterfactual set delta; Ruff; and `git diff --check`.

### 2026-08-31 — review bucket and widened mechanisms

- P40 bucket: the review's changed-only sentinel escape and one-way root census are the
  same `P35`/`P37`/`P38` class one level deeper, not new classes. The repair therefore
  widened each mechanism to the quantity its property needs: Git worktree-relative path
  identity for every changed file and set equality between declared roots and real
  Python package roots. It did not add per-path exceptions.
- Unsupported policy versions were a same-class authority bypass: the contract's version
  field could switch off its own governance. The linter now admits exactly version `2`;
  both `1.0` and `2.0` mutation probes fail before imports are scanned. The two isolated
  legacy fixtures were migrated to complete v2 direction/ownership contracts instead of
  receiving a test-only bypass.
- The boundary register's own version was the same authority-bypass class one layer
  deeper. It now admits exactly integer version `2`; missing, legacy, future, float, and
  string variants fail before ownership or narrowing rows are interpreted.
- The final root-denominator falsifier found that `__init__.py` was still a proxy for the
  linter's actual scan. Root coverage now derives from every path returned by
  `iter_py_files()`, using the same `module_name_for_path()` normalization as import
  parsing; ordinary packages, namespace-style directories, and root-level modules all
  enter the declared-root equality check.
- Changed-only canon: `git rev-parse --show-toplevel` establishes the path root; both
  tracked-diff and untracked names are resolved exactly once against that root. Missing
  worktree identity, a non-commit base, a failed diff, a failed untracked census, or a
  command-launch error is an exit-2 gate failure, never an empty change set.
- DS18 verification was widened from the local edge witness to a whole-graph
  counterfactual: inject only the historical Monitors -> Incident import into the real
  AST collector, canonicalize both complete SCC sets, and assert exactly the two-module
  tuple is added in the counterfactual and no current tuple is absent from it.

## Canonical censuses and rulings

### Import direction and package coverage

- Complete source-root denominator: 2,611 paths from `iter_py_files()` normalized by
  `module_name_for_path()` to 25 distinct second-segment roots, 25 `[roots].known`
  values, and 25 `[internal.allow]` rows. A root-level `polisyos/<name>.py` contributes
  `<name>`; `polisyos/__init__.py` contributes no root. Canon: sorted exact root names;
  set differences are empty in all three directions.
- Package governance denominator: those same 25 exact roots. Eighteen have an exact
  `[[package]]` row with a `team-*` owner; seven have a nonblank
  `[[deliberately_ungoverned_root]]` reason. Canon: sorted exact root names; governed and
  ungoverned sets are disjoint and their union equals the direction denominator.
- Removed nonexistent roots: five root rows and one residual target reference —
  `academic`, `batch_common`, `batch_snapshot`, `datasets`, `ukraine_data`; strict-root
  postcondition is zero matrix roots without a directory.
- Remaining narrowings: canonical form is sorted JSON rows
  `{source_root,target_root,sorted minimal allowed_prefixes}`. Five rows, SHA-256
  `278e3ade7393a3f58a721f9b104e13a5621203f0f734c66ef0787adea27d2856`:
  Fabric, Foundry, IR, Lex, and Scientist -> Data Forge, each admitted only through
  `polisyos.data_forge.read_api`.

### Scientist and Runtime

Canonical form: sorted JSON statement rows
`{path,line,source_module,target_modules,ordered aliases,scope}` over every Python file
returned by `Path("src/polisyos/<root>").rglob("*.py")`; `scope` is `module`, `class`, or
`deferred`. Counts therefore name their measures rather than standing alone.

- Scientist -> Runtime: 584 Python files examined; 13 import statements, 34 imported
  aliases, 11 importing files; 11 module-scope + 0 class-scope + 2 deferred statements;
  canonical-row SHA-256
  `d46516dbdca244ab29ef675ec3cd24704ce3d6716e91cb3de3b65847e86ba56f`.
- Runtime -> Scientist: 280 Python files examined; 74 import statements, 115 imported
  aliases, 28 importing files; 33 module-scope + 0 class-scope + 41 deferred statements;
  canonical-row SHA-256
  `cd1a3ad5cdcc66dbdec98cf9d15e228c3d2b1c0c6ec0ad2b8c2f78a294389e3c`.
- Reconciliation of the inherited 276: the pattern
  `git ls-files 'src/polisyos/runtime/**/*.py'` returns 276 tracked files but omits the
  four root-level files `runtime/__init__.py`, `runtime/api.py`, `runtime/manifest.py`,
  and `runtime/replay.py`. The last contributes five of the 74 Runtime -> Scientist
  statements. The explicit root-plus-recursive tracked set and `Path.rglob` both return
  280. Therefore 276 is a proxy denominator, not the canonical corpus.
- Ruling: Runtime may consume Scientist; Scientist must not consume Runtime. The measured
  weight is 74 statements versus 13 (5.69:1). The existing mutual direction remains
  `open` until the 13 reverse statements are owner-relocated; deleting the permission
  before that migration would only turn every lane's gate red.

### Core observability

Canonical form: sorted JSON cross-package statement rows
`{path,line,source_root,sorted targets,ordered imported names}` over 2,611 Python files.
SHA-256 `91d7c9d44fc066fc0b945edaa781d7eb45e2de22549f1b06259f06d7875336b6`.

- Current corpus: 251 cross-package statements in 219 files, 304 imported-name
  occurrences; 67 exact-facade statements and 184 deep statements.
- Deep decisions: determinism is 166 statements / 165 files / 169 name occurrences;
  truthfulness is 11 / 9 / 25; the HPC config helper is 2 / 2 / 2; pricing is 2 / 2 / 2;
  propagation is 3 / 3 / 3.
- The register's 252-statement / 220-file / 185-deep corpus is stale by exactly the IR
  truthfulness bridge relocated after that row was measured.
- Ruled in this wave: (1) promote the three determinism names through the exact Core
  observability facade, then re-spell 166 Foundry statements; (2) promote
  `is_hpc_observability_enabled` through that same facade, then re-spell two Foundry
  statements. These are rulings, not bulk execution.
- Left: truthfulness needs explicit IR/Core owner adjudication; the five already-covered
  pricing/propagation statements are mechanically ready but unexecuted. Final contract,
  inventory, deferred-set, and deep-baseline reconciliation follows only after all deep
  consumers are gone. `fabric/_adapters/observability.py` was not touched.

### DS18 cycle canon

Canon is a sorted tuple of sorted module FQNs, not a comparison of counts. At base there
were 16 total SCC tuples, SHA-256
`4c925895cfab8d0b6bf2bf7c0c7309b8ae4434ea86f422556bf571087a85d7d2`, of which four
were new-cycle findings. After the owner move there are 15 total tuples, SHA-256
`673bc17dfbfb62e578772c4e33ef0d66c9ad208875a27ff535b8cdeb13453668`, of which three
are findings. Set subtraction contains exactly one tuple:
`(polisyos.scientist.governance.continuous.incident,
polisyos.scientist.governance.continuous.monitors)`; set addition is empty. No cycle
predicate, allowed-cycle registry, exception, or witness changed.

## Tightened gates — hand-back to concurrent lanes

The import linter now loads the package register named by a version-2 direction matrix,
adds that file to changed-scan sentinels and cache fingerprints, and fails closed on these
rules. The diagnostic text below is verbatim; braces name substituted values. The CLI
prefixes configuration-load failures with `Config error: ` and then the exact detail
listed here.

1. Matrix schema and references:
   - Exact version rule: only `2` is admitted; every other value fails before scanning.
   - `unsupported import policy version {version!r}; supported versions: 2`
   - `internal.allow must be a table`
   - `internal.allow rows missing from roots.known: {roots}`
   - `internal.allow.{root} must be defined`
   - `internal.allow.{root} names unknown roots: {roots}`
   - `policy.contract_role must be 'enforced_direction_matrix' for policy version 2`
   - `policy.package_boundaries must name the ownership/narrowing register`
   - `Package boundary register not found: {path}`
   - `direction matrix roots without directories: {roots}`
   - Exact root canon: every Python path returned by `iter_py_files()` is normalized by
     `module_name_for_path()`; the first module segment after `<internal-prefix>` is a
     real root, including namespace-style directories and root-level modules. Its sorted
     set must equal the direction-root set.
   - `direction matrix missing source package roots: {roots}`
2. Ownership/narrowing register schema and complete coverage:
   - Exact version rule: `[package_boundaries].version` must be integer `2`.
   - `package_boundaries.version must be 2, got {value!r}`
   - `package_boundaries.contract_role must be 'ownership_and_narrowing_register'`
   - `package boundary register [[package]] entries must be a list`
   - `package boundary register contains a non-table package entry`
   - `package boundary root {root} is not in direction matrix`
   - `package boundary root {root} must name a team-* owner`
   - `duplicate exact-root package boundary: {root}`
   - `[[deliberately_ungoverned_root]] entries must be a list`
   - `deliberately ungoverned root entry must be a table`
   - `deliberately ungoverned root is not in direction matrix: {root}`
   - `deliberately ungoverned root {root} must state a reason`
   - `duplicate deliberately ungoverned root: {root}`
   - `direction roots cannot be both governed and deliberately ungoverned: {roots}`
   - `package governance missing for direction roots: {roots}`
   - `package boundary root {source_root} allowed_dependencies must be a list`
   - `package boundary root {source_root} has a non-string dependency`
3. Edge narrowing, applied only after the direction matrix admits the root pair:
   - Exact rule: a target must equal or descend from a registered minimal prefix; for
     `from <target-root> import ...`, every imported name must resolve under a registered
     prefix and wildcard/root-wide imports fail.
   - Exact diagnostic:
     `{path}:{line} [ARCH007] forbidden narrowed internal import: {source_root} ->
     {target_root} via {target_module} (allowed_prefixes={comma-separated-prefixes})`.
4. Changed-only execution:
   - Exact rule: canonicalize all Git names against the worktree root returned by
     `git rev-parse --show-toplevel`; a policy, exception, linter, or configured boundary
     sentinel forces a full scan. Indeterminate Git state fails with exit 2.
   - `changed-only Git command failed: {error}`
   - `changed-only Git worktree root is unavailable: {error}`
   - `changed-only Git base ref is not a commit: {base_ref}`
   - `changed-only Git diff failed: {error}`
   - `changed-only Git untracked-file census failed: {error}`

No existing diagnostic was loosened. No import exception was added, renewed, or consumed;
the real-tree report records zero allowed exceptions.

## Out-of-scope findings, not acted on

- Public-surface contract ownership for `polisyos.fabric.world`; neither the aggregate
  contract nor its generated inventory/baseline is in this lane.
- The 13 Scientist -> Runtime source statements and their owner-side relocation.
- Runtime's proving-ground fixture validator, its registration/projection definition, and
  the absent Corpus package-owner appointment.
- The 166 determinism, 11 truthfulness, two HPC, and five pricing/propagation consumer
  edits plus final observability public-contract/inventory reconciliation.
- Three other current non-lazy SCC findings, unchanged by the exact DS18 set diff.
- The `test_monitors.py` control-plane collection cycle reproduced at the task base before
  this lane's module is imported.
- Six docs-lifecycle findings in architect/Atlas/frontend/research-owned files.
- Bound debt-ledger closure-signal identities and the architect-only ledger pin.
- `tools.lib.cache.git_changed_files` remains a permissive shared helper that assumes its
  caller supplied the Git top level and maps failed diffs to an empty set. This lane did
  not modify that out-of-scope owner; the import gate uses a local fail-closed adapter.
  Its falsifier returned 12 paths relative to the Task F base: all 12 had a doubled
  `policy-engine/policy-engine/` prefix and zero existed; canonical path-list SHA-256 is
  `bb811d1f5c70c1a470bfbc71ee9a8bbbae4132102175a417ba5a0f09d439c1ed`.
  The smallest absent capability is a shared helper that derives the Git top level,
  propagates diff/untracked failures, and has consumer tests for both the import linter
  and schema generator. Consolidating that owner later would retire the bounded P27
  duplication risk; `tools/lib/cache.py` and `gen_schema.py` are outside this task's
  explicit owned-file set.
- `architecture/atlas_surfaces/**`, the debt register, LEDGER, GY plan, Atlas master plan,
  and `fabric/_adapters/observability.py` remain untouched.

## Register closure dossier

Arithmetic: **7 rows = 3 closed + 2 open + 2 blocked + 0 ambiguous**.
Core: **5 = 2 closed + 2 open + 1 blocked + 0 ambiguous**.
Adjacent: **2 = 1 closed + 0 open + 1 blocked + 0 ambiguous**.

### `import-authority-files-diverge` — closed

- Verdict: `closed`.
- Exact command/predicate: `.venv/bin/python -m pytest -q
  tests/repo_quality/architecture/test_import_governance_contract.py::test_import_authority_contracts_declare_distinct_canonical_roles
  tests/repo_quality/architecture/test_import_governance_contract.py::test_five_remaining_narrowings_have_one_canonical_form
  tests/repo_quality/tools/test_lint_imports_phase3.py::test_lint_imports_allows_only_the_registered_submodule_of_an_allowed_root
  tests/repo_quality/tools/test_lint_imports_phase3.py::test_lint_imports_resolves_parent_from_import_to_registered_submodule
  tests/repo_quality/tools/test_lint_imports_phase3.py::test_lint_imports_rejects_sibling_of_registered_narrowing`
  — exit 0.
- Exact append-only prose:
  “2026-08-31 supersession — **closed**. Executed the 2026-08-26 ruling:
  `architecture/imports/policy.toml` declares and enforces the root direction matrix;
  `architecture/packages/boundaries.toml` declares ownership and dependency narrowings.
  The linter consumes both and canonically enforces the five remaining strict-root pairs:
  Fabric, Foundry, IR, Lex, and Scientist -> Data Forge only through
  `polisyos.data_forge.read_api`. Positive exact-facade and parent-from-import cases pass;
  a sibling `data_forge.kernel` target fails with ARCH007. Zero exceptions were added or
  renewed.”

### `package-boundaries-coverage-gap` — closed

- Verdict: `closed`.
- Exact command/predicate: `.venv/bin/python -m pytest -q
  tests/repo_quality/architecture/test_import_governance_contract.py::test_every_direction_root_exists_and_has_package_governance_disposition
  tests/repo_quality/tools/test_lint_imports_phase3.py::test_version_two_policy_fails_closed_on_missing_governance_disposition
  tests/repo_quality/tools/test_lint_imports_phase3.py::test_version_two_policy_fails_closed_on_nonexistent_direction_root
  tests/repo_quality/tools/test_lint_imports_phase3.py::test_version_two_policy_fails_closed_on_undeclared_scanned_root
  tests/repo_quality/tools/test_lint_imports_phase3.py::test_version_two_policy_rejects_unsupported_boundary_version
  tests/repo_quality/tools/test_lint_imports_phase3.py::test_version_two_policy_rejects_extra_exact_root_boundary`
  — exit 0. Predicate denominator is 25 real direction roots = 18 exact owned package
  roots + 7 reasoned deliberately-ungoverned roots; zero nonexistent matrix roots.
- Exact append-only prose:
  “2026-08-31 supersession — **closed**. Removed five nonexistent roots from the direction
  matrix and its allow rows; the strict-root rerun reports zero matrix rows without a
  directory. All 25 scanner-derived Python roots now have a package-governance
  disposition: 18 exact
  `[[package]]` roots name `team-*` owners and seven are explicitly deliberately ungoverned
  with nonblank reasons; Corpus remains unappointed rather than receiving an inferred
  owner. The stale nonexistent `package_boundaries.py` claim is gone. The register names
  its actual fail-closed readers, and `lint_imports.py` enforces role, path, directory,
  owner/reason, overlap, and two-way complete-coverage invariants. Changed-only execution
  derives paths from the Git worktree root and fails closed on an indeterminate census.”

### `scientist-runtime-declared-cycle` — open

- Verdict: `open`, retyped from `blocked`; the missing census blocker is discharged and
  the direction is ruled, but the reverse-edge migration is not in this lane.
- Exact predicate: complete `Path.rglob("*.py")` AST census with sorted canonical statement
  rows; exit 0 after asserting Scientist -> Runtime = 584 files / 13 statements / 34
  aliases / 11 importing files and Runtime -> Scientist = 280 / 74 / 115 / 28, with the
  hashes recorded above.
- Exact append-only prose:
  “2026-08-31 supersession — **open; direction ruled**. The missing reverse census now
  exists and is reproduced over the complete corpus: Scientist -> Runtime is 13 statements
  / 34 aliases / 11 files across 584 Python files; Runtime -> Scientist is 74 / 115 / 28
  across 280 Python files. The inherited 276 proxy omitted four Runtime root files,
  including five statements in `runtime/replay.py`. Rule Runtime -> Scientist as the
  retained direction (74:13, 5.69:1); migrate the 13 Scientist -> Runtime statements, then
  remove that permission. Do not remove it before the source migration and do not add an
  exception.”

### `fabric-world-facade-enforcement-conflict` — blocked

- Verdict: `blocked` on the shared public-surface owner; the target rule is established.
- Exact predicate: a behavioral temp-policy run admits the exact
  `polisyos.fabric.world` import with source-lint exit 0 and zero violations, while
  `guardrails.collect_deep_import_edges()` classifies the canonical
  `polisyos.runtime.quality.data_state_substrate -> polisyos.fabric.world` edge as deep;
  combined predicate exit 0.
- Exact append-only prose:
  “2026-08-31 supersession — **blocked on shared public-surface ownership; rule fixed**.
  ARCH004 advertises and admits exact `polisyos.fabric.world`, while the release collector
  classifies the same canonical edge as deep because the aggregate public contract omits
  it. The common definition must admit exactly the world facade and reject external
  descendants; both guards must derive from that definition. Closure requires the
  public-surface owner to add the exact entrypoint and migrate remaining descendant
  imports. Deleting the Phase-0 witness or exporting `create_world_snapshot` is not
  closure and was not done.”

### `core-observability-canonical-interface-contract-drift` — open

- Verdict: `open`, bounded partial; `surface_missing` + `verification_missing`.
- Exact predicate: complete 2,611-file AST census in the canonical form above; exit 0 with
  251 statements / 219 files / 304 imported-name occurrences, split 67 exact + 184 deep,
  SHA-256 `91d7c9d44fc066fc0b945edaa781d7eb45e2de22549f1b06259f06d7875336b6`.
- Exact append-only prose:
  “2026-08-31 supersession — **open; two bounded decisions ruled**. Fresh complete AST
  census corrects the subject to 251 cross-package statements in 219 files (67 exact,
  184 deep); the prior 252/220/185 corpus predates the IR bridge relocation. Rule
  determinism's three names into the exact Core observability facade before re-spelling
  166 Foundry statements. Rule `is_hpc_observability_enabled` into the same facade before
  re-spelling two Foundry statements. Truthfulness remains an explicit IR/Core owner
  adjudication; five already-covered propagation/pricing statements remain mechanical
  re-spellings. Only after those decisions execute may closure add exactly
  `polisyos.core.observability`, remove its deferred marker, and reconcile inventory and
  baseline. The Fabric adapter remained untouched.”

### `import-policy-governance-runtime-corpus-dependency` — blocked

- Verdict: `blocked` on the absent Corpus package owner; direction is ruled and the
  relocation itself remains executable.
- Exact predicate: complete Runtime AST scan canonicalized as sorted
  `{path,line,target,ordered symbols}` rows; exit 0 with 1 statement / 1 file / 2 symbols,
  SHA-256 `63eef5900390a25b77e1c302c78ef72b14b70049c9ab42e9dbfa81430e130fcb`.
  Base and final full-source lint both emit the same line-560 ARCH001 violation.
- Exact append-only prose:
  “2026-08-31 supersession — **blocked only on the unappointed Corpus package owner;
  direction ruled**. Runtime -> Corpus remains forbidden. The complete edge is one
  deferred statement in one Runtime worker importing two evaluation-fixture loader
  symbols. Relocate `_validate_proving_ground`, the `legacy-proving-ground` registration,
  and its projection definition to tools/tests; do not create a Runtime/Corpus allowance
  or persisted authority artifact. Under the custody ruling the empty owner slot binds
  the claim, not the relocation capability.”

### `ds18-continuous-incident-monitors-static-cycle` — closed

- Verdict: `closed`.
- Exact command/predicate: `.venv/bin/python -m pytest -q
  tests/repo_quality/architecture/test_continuous_incident_import_cycle.py
  tests/unit/scientist/governance/continuous/test_incident.py` — exit 0, five tests passed.
  Canonical SCC set subtraction is exactly the Incident/Monitors tuple; addition is empty;
  new-cycle findings move 4 -> 3.
- Exact append-only prose:
  “2026-08-31 supersession — **closed**. Moved the incident-specific persistence bridge
  from `monitors.py` to the Incident owner, preserving strict CAS persistence, readback,
  perturbation binding, and review-required posture. Canonical sorted SCC comparison
  removes exactly `(continuous.incident, continuous.monitors)` and adds no tuple; the
  report-only new-cycle finding measure returns from four to three. No cycle predicate,
  lazy-cycle registry, exception, or witness was changed.”

## Round 2 evidence journal

### 2026-08-31 — resumed execution basis

- Resumed attached to `codex/debt-f-architecture-imports` at
  `a82913599cee53573aa9e0527ee6e5b89a6f0faf`; the worktree was clean and the merge base
  remained `784d020148c56e9bfb3a3631909ba11232210a9f`.
- Re-read the round-1 dossier, contributor contract, and PDC failure/repair register
  before appending the round-2 plan. The user accepted the three round-1 closures and
  corrected denominators to 584 Scientist / 280 Runtime Python files and 251 current
  cross-package observability statements.
- Round-2 interpretation: “mechanical work done” covers every already-ruled observability
  move — 166 determinism statements, two HPC-config statements, and five already-facaded
  pricing/propagation statements. The only intended deep remainder is the separately
  adjudicated truthfulness family.
- P37 labels at admission: live AST/path censuses are `recomputed`; the direction and
  exact-facade rulings are `institutionally_supplied` but ratified for execution; the
  truthfulness destination decision and Corpus owner appointment are `not_established`
  and cannot authorize closure. P38 property/proxy split: counts are observations only;
  closure turns on canonical row-set emptiness or exact residual identity, never on a
  count changing by the expected amount.

## 2026-08-31 — round-2 execution and terminal measurement

### Delivered implementation

- `28501c5eb` consolidates changed-file discovery in the shared fail-closed Git-root
  helper and wires both the import linter and ABI schema generator to it. Ten focused
  cases cover nested invocation, caller-relative pathspecs, tracked and untracked product
  files, the two consumers, and five indeterminate Git states.
- `3637332e0` makes the import linter and release collector derive the Fabric-world
  boundary from the same exact `polisyos.fabric.world` contract. The four Runtime-used
  write identities were already curated facade exports. `create_world_snapshot` remains
  private, the Phase-0 witness remains present, and external `.store` imports remain
  forbidden. The synchronized deep-import baseline changed by exactly 12 deletions, all
  former edges to the newly registered exact facade, and by zero additions.
- `13384cf9e` executes every ruled observability migration: 173 Python import statements
  across 172 files plus the previously uncounted `foundry/methods/base.pyi` companion.
  The split is 166 determinism statements, two HPC-helper statements, two pricing
  statements, and three propagation statements. The exact residual is now only the
  truthfulness adjudication.
- `70186047e` migrates every Scientist -> Runtime statement whose owner ruling was
  settled. Replay now has a Scientist-owned deterministic implementation with Runtime
  retaining an exact identity-preserving compatibility facade. `WorldModelRecord` and
  its content-hash identities are PDC-owned while Runtime retains construction,
  resolution, persistence, and compatibility identities. Production-approval
  currentness is a sealed, content-bound Core receipt minted from live state by Runtime
  and verified by Scientist without a Runtime import; raw mappings, callbacks, and
  projection DTOs fail closed.
- Zero import exceptions were added, renewed, or consumed. No witness was deleted, no
  private factory was exported, and no predicate was loosened.

### Scientist / Runtime census and the remaining owner decision

The direction canon is a complete `Path.rglob("*.py")` AST walk. Each statement is one
row containing source-relative path, source module, exact target-module sequence, ordered
`{name, asname}` alias sequence, and structural scope (`module`, `class`, or `deferred`).
Rows sort by `(path, line)` and serialize as compact sorted-key JSON encoded as UTF-8,
with no wrapper or trailing newline. The residual guard deliberately drops line number
from identity and compares source-relative path, exact target, alias sequence, and
module/deferred scope, so harmless line drift cannot masquerade as an architecture
change.

At committed pre-migration head `13384cf9e`:

- Scientist -> Runtime: 584 Python files / 13 import statements / 34 aliases / 11
  importing files; 11 module-scope + 0 class-scope + 2 deferred statements; SHA-256
  `442c9d20ea194850df7565077bf203e84f910deb18f584c0469b6d6a1136c8d0`.
- Runtime -> Scientist: 280 Python files / 74 import statements / 115 aliases / 28
  importing files; 33 module-scope + 0 class-scope + 41 deferred statements; SHA-256
  `cd1a3ad5cdcc66dbdec98cf9d15e228c3d2b1c0c6ec0ad2b8c2f78a294389e3c`.
- The direction weight is 74:13 statements, or 5.69:1. The 280-file denominator includes
  all four Runtime root-level files; `runtime/replay.py` contributes five statements.

At final head `70186047e`:

- Scientist -> Runtime: 585 Python files / 7 import statements / 15 aliases / 5
  importing files; all seven module-scope; SHA-256
  `0b4b849b1db24f57675000f250568c7801d7ab9b7138a252eba9db6ec7dcb60e`.
  The file denominator grew by the new canonical Scientist replay module.
- Runtime -> Scientist: 280 Python files / 70 import statements / 110 aliases / 28
  importing files; 34 module-scope + 0 class-scope + 36 deferred statements; SHA-256
  `b9f4d687adb2ff88b447bdcd945a665c396f12d244ba65acd3512fcf92867294`.

Six whole reverse statements moved: two replay statements moved to the Scientist replay
owner; two standalone `WorldModelRecord` statements moved to the PDC owner; and two
deferred approval-resolver statements became receipt verification through the exact Core
contracts facade. In addition, two retained EvalSafety statements shed the three
non-EvalSafety aliases (`WorldModelRecord`, `gy_content_hash`, and
`world_model_record_content_hash`) to PDC. The exact seven-statement residual is:

1. `scientist/api.py:49` -> `polisyos.runtime.quality`:
   `EvalSafetyVerifierPort`, `EvaluationExecutionContext`.
2. `scientist/nodes/builtins/decide/policy_runtime_support.py:31` ->
   `polisyos.runtime.quality`: `EvalSafetyAdmissionChallenge`,
   `evaluation_safety_consumer_admission_is_verified`, `resolve_evaluation_mode`.
3. The same file at line 81: `EvalSafetyVerifierPort`,
   `EvaluationExecutionContext`.
4. `scientist/nodes/builtins/simulate/run_causal_evaluation.py:39`:
   `EvalSafetyAdmissionChallenge`,
   `evaluation_safety_consumer_admission_is_verified`, `resolve_evaluation_mode`.
5. The same file at line 73: `EvaluationExecutionContext`.
6. `scientist/orchestration/engine/context.py:11`: `EvalSafetyVerifierPort`,
   `EvaluationExecutionContext`.
7. `scientist/orchestration/workflows/builder.py:74`: `EvalSafetyVerifierPort`,
   `EvaluationExecutionContext`.

This is one contract: five unique EvalSafety names, seven statements, 15 aliases, five
files. The authoritative GY task-standing table at
`docs/plans/active/layer3-slices/GY-engine-subordination.md:1610` appoints executed task
`GY-O0` to `runtime/quality`; the detailed task at line 5143 defines EvalSafety as the
pre-execution attempted-evaluation safety gate. The architect must therefore ratify one
of this binary before the permission can disappear:

1. move the complete `GY-O0` EvalSafety owner to Scientist; or
2. move the complete Scientist evaluation-execution choke into Runtime.

Until that ruling lands, `scientist -> runtime` remains permitted only for the structurally
pinned seven statements. PDC's stale reverse permissions to Runtime and Scientist were
removed because PDC imports neither. No exception stands in for the ruling.

### Observability terminal measurement

The pre-migration complete-AST canon remains 2,611 Python files / 251 cross-package
observability statements / 219 files / 304 imported-name occurrences, split 67 exact and
184 deep, SHA-256
`91d7c9d44fc066fc0b945edaa781d7eb45e2de22549f1b06259f06d7875336b6`.
After the 173 ruled Python re-spellings and the `.pyi` companion, the exact residual is 11
statements in nine files, 25 imported-name occurrences, and ten unique names:
`TruthfulnessReceipt`, `TruthfulnessScope`, `TruthfulnessStatus`, `TruthfulnessTier`,
`extract_truthfulness_receipt`, `parse_truthfulness_scope`,
`parse_truthfulness_tier`, `reconcile_truthfulness_tiers`, `truthfulness_depth`, and
`validate_truthfulness_receipt`.

The closure counterfactual is decisive rather than numerical: treating
`polisyos.core.observability` as closed makes
`test_phase1_5_closed_public_canonical_interfaces_use_exact_facades` enumerate 11 deep
imports, not the required empty canonical set. Therefore the deferred marker cannot be
removed and the exact facade cannot be added to the public contract while the eleven
remain. The row is blocked on the IR/Core/Foundry/Architecture owner adjudication of
whether IR-owned truthfulness identities project through the Core observability facade
or the nine Foundry consumers route through an admitted IR facade. The Fabric adapter
was not touched.

### Six-lane tightened-gate overlay

Method: for each immutable reported head, archive the branch, overlay this lane's final
`lint_imports.py`, `tools/lib/cache.py`, version-2 policy, exceptions file, and package
register, then run a full source scan. Intersect ARCH007 results with the complete
merge-base-to-head changed Python path set. A successful version-2/register load proves
the version and root-coverage conjuncts. Each scan exited 1 only for the inherited
Runtime -> Corpus ARCH001 statement at line 560; none of the changed paths contained that
row and none emitted ARCH007. Therefore all three tightened rules are green for all six
lanes at these exact heads:

| Lane | Measured head | Changed paths / Python / source Python | ARCH007 | policy v2 | root coverage |
| --- | --- | ---: | --- | --- | --- |
| A | `16115c81f089b8796866e0cce52930ed263cde3e` | 7 / 4 / 2 | green | green | green |
| B | `828d97977665e8bbbde7ea4a5402e0b9f0fb2efc` | 5 / 3 / 1 | green | green | green |
| C | `c0d6f14156b8e64a9769fa4e218410e768874a5f` | 2 / 0 / 0 | green (not exercised) | green | green |
| D | `fb4a672dcb58b1e193cb1a24984df7872361ee0c` | 25 / 4 / 0 | green (not exercised) | green | green |
| E | `066e1978ac1c2bf82f790446dd23d8f607780122` | 7 / 4 / 2 | green | green | green |
| G | `79dd433834eaa3f59e940aa69cec5509b5b93bed` | 8 / 4 / 0 | green (not exercised) | green | green |

A and E were live; their heads advanced after the first overlay and were re-measured at
the heads above. B, C, D, and G remained at their frozen heads. No cross-lane opinion or
branch state was used to decide a Task F verdict.

### Scientist paths changed since the slice base

Task B's later merge must reconcile these 17 paths:

1. `src/polisyos/scientist/api.py`
2. `src/polisyos/scientist/artifacts/decision_compiler.py`
3. `src/polisyos/scientist/governance/continuous/incident.py`
4. `src/polisyos/scientist/governance/continuous/monitors.py`
5. `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py`
6. `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`
7. `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py`
8. `src/polisyos/scientist/orchestration/engine/runner/_activity_worker.py`
9. `src/polisyos/scientist/orchestration/engine/runner/ray_runner.py`
10. `src/polisyos/scientist/orchestration/engine/runner/temporal_runner.py`
11. `src/polisyos/scientist/orchestration/llm/budget_enforcer.py`
12. `src/polisyos/scientist/replay/AUTHORING.md`
13. `src/polisyos/scientist/replay/README.md`
14. `src/polisyos/scientist/replay/backend.py`
15. `src/polisyos/scientist/replay/deterministic.py`
16. `src/polisyos/scientist/replay/verification.py`
17. `src/polisyos/scientist/validation/decision_artifact_quality.py`

### Final verification and inherited red

- 29 exact migration/governance/replay/WMR/approval cases: exit 0, 29 passed.
- Five exact Fabric/DS18 cases: exit 0, five passed.
- `PYTHONPATH=. .venv/bin/python tools/devx/architecture/guardrails.py check
  --skip-generated-checks`: exit 0.
- `.venv/bin/python -m ruff check` over every changed migration Python path: exit 0.
- `git diff --check`: exit 0 before the dossier-only append.
- Full import scan with the final version-2 contract: exit 1 with exactly one violation,
  the already recorded Runtime -> Corpus statement at line 560; zero allowed exceptions.
- Bound `check_debt_ledger.py --check`: exit 1 with exactly 18 blocking
  `closure_signal_identity_unresolvable` findings and 18 count/exit disagreements: nine
  `ds10-*`, eight `DS11-*`, and one decision-validity row. The blocker set did not grow.
- Bound `check_docs_lifecycle.py`: exit 1 with exactly six inherited findings. This
  journal names none of the stale-path literals that would create a seventh.
- One pre-existing approval-quality test remains red at `5 != 2`. The identical failure
  was reproduced from committed pre-migration head `13384cf9e`; the new content-bound
  approval receipt cases and issuer guard are green.

### Gate changes that merge ahead of the other lanes

The round-1 version-2, root-coverage, ARCH007, and changed-only diagnostics listed above
remain exact. Round 2 adds or narrows these rules; no diagnostic was weakened:

1. Fabric-world exact facade. External consumers may import exactly
   `polisyos.fabric.world`; `.store` and `.materialize` descendants remain private. Exact
   diagnostic:
   `{path}:{line} [ARCH004] forbidden deep import: {source_module} -> {target_module}. Use polisyos.fabric.world facade exports.`
   The behavioral witness is the concrete diagnostic
   `[ARCH004] forbidden deep import: polisyos.runtime.sample -> polisyos.fabric.world.store. Use polisyos.fabric.world facade exports.`
2. PDC direction tightening. PDC may import only `{common, core, ir, pdc}`; its former
   Runtime and Scientist permissions are removed. Exact diagnostics are:
   `{path}:{line} [ARCH001] forbidden internal import: pdc -> runtime via {target_module} (allowed={common, core, ir, pdc})`
   and
   `{path}:{line} [ARCH001] forbidden internal import: pdc -> scientist via {target_module} (allowed={common, core, ir, pdc})`.
3. EvalSafety residual pin. The exact allowed Scientist -> Runtime structural row set is
   the seven rows enumerated above, including alias order and scope, and the total alias
   measure is exactly 15. This is a pytest structural assertion, not a new CLI rule; its
   diagnostic identifier is
   `test_scientist_runtime_residual_is_exact_eval_safety_owner_ruling`, followed by
   pytest's exact row-set or `15` alias-count diff.
4. Observability residual pin. The only permitted cross-package deep observability rows
   are the eleven enumerated truthfulness statements, and the `.pyi` companion must use
   the exact facade. This is a pytest structural assertion; its diagnostic identifier is
   `test_observability_deep_import_residual_is_exact_truthfulness_adjudication`, followed
   by pytest's exact row-set diff.
5. DS18 canonical SCC pin. The gate compares the sorted tuple set itself: the
   Incident/Monitors tuple must be absent, the other three finding tuples must be
   byte-identical, and additions must be empty. This is a pytest structural assertion;
   its diagnostic identifier is
   `test_incident_monitor_bridge_removes_exactly_its_static_scc`, followed by the exact
   missing/added tuple-set diff.

The shared Git helper also makes both changed-only consumers fail closed with these exact
new diagnostics:
`changed-only Git command failed: {error}`;
`changed-only Git worktree root is unavailable: {error}`;
`changed-only Git base ref is not a commit: {base_ref}`;
`changed-only Git diff failed: {error}`;
`changed-only Git untracked-file census failed: {error}`; and the schema consumer wraps
the same condition as `ABI schema snapshot generation failed: {exc}`.

Bounded residual, not acted on: the shared helper consumes newline-delimited Git output,
so a tracked filename containing a literal newline is not representable. The smallest
closure is NUL-delimited `-z` parsing in the one owner, with both consumers retaining the
same tests. No production path in this slice depended on that hostile-name case.

## Register closure dossier — round-2 supersession

Arithmetic: **7 rows = 4 closed + 3 blocked**.
Core: **5 rows = 3 closed + 2 blocked**.
Adjacent: **2 rows = 1 closed + 1 blocked**.

### `import-authority-files-diverge` — closed

- Verdict: `closed`.
- Deciding command/predicate: the five exact contract/narrowing nodes under
  `test_import_governance_contract.py` and `test_lint_imports_phase3.py`; exit 0. Canon is
  the strict-root pair mapped to its sorted minimal allowed module-prefix set, not a
  textual TOML diff. Five narrowed pairs remain and both version-2 contracts declare
  their distinct ratified roles.
- Exact append-only prose:
  “2026-08-31 round-2 supersession — **closed**. The version-2 direction matrix and
  ownership/narrowing register retain their ratified distinct roles, and the linter
  enforces their single mapped canon. The five remaining strict-root narrowings are
  recorded and green; zero exceptions were added, renewed, or consumed.”

### `package-boundaries-coverage-gap` — closed

- Verdict: `closed`.
- Deciding command/predicate: the six exact governance-coverage and version-2 failure
  nodes under `test_import_governance_contract.py` and `test_lint_imports_phase3.py`;
  exit 0. Complete scanner-derived denominator: 25 real direction roots = 18 exact
  `team-*`-owned package roots + seven reasoned deliberately-ungoverned roots; zero
  nonexistent matrix roots and zero undisposed real roots.
- Exact append-only prose:
  “2026-08-31 round-2 supersession — **closed**. The strict-root directory census remains
  zero nonexistent rows. All 25 real roots have exactly one governance disposition: 18
  appointed `team-*` owners and seven explicit deliberately-ungoverned reasons. The
  register names the real fail-closed readers, and the version-2/root-coverage overlay is
  green on all six other lane heads.”

### `scientist-runtime-declared-cycle` — blocked

- Verdict: `blocked`.
- `blocked_by`: architect re-ratification of the complete `GY-O0` EvalSafety ownership
  boundary: either move the complete owner to Scientist or move the complete execution
  choke to Runtime.
- Deciding command/predicate:
  `.venv/bin/python -m pytest -q tests/repo_quality/architecture/test_import_governance_contract.py::test_scientist_runtime_residual_is_exact_eval_safety_owner_ruling`
  — exit 0. The independent full-AST canon at final head is 585 Scientist files / seven
  statements / 15 aliases / five files, SHA-256
  `0b4b849b1db24f57675000f250568c7801d7ab9b7138a252eba9db6ec7dcb60e`.
- Exact append-only prose:
  “2026-08-31 round-2 supersession — **blocked by an architect ruling that must land**.
  Six of the 13 Scientist -> Runtime statements migrated without an exception: Replay to
  Scientist, WorldModelRecord to PDC, and approval currentness to a sealed Core receipt
  minted by Runtime and verified by Scientist. The exact residual is one EvalSafety
  contract: seven statements, 15 aliases, five files, structurally pinned. GY-O0's
  authoritative task row appoints `runtime/quality`; closure therefore requires
  re-ratifying either the complete owner into Scientist or the complete execution choke
  into Runtime. Scientist -> Runtime remains permitted only for this residual until that
  decision lands. PDC's two stale reverse permissions are removed. Zero exceptions were
  added or renewed.”

### `fabric-world-facade-enforcement-conflict` — closed

- Verdict: `closed`.
- Deciding command/predicate:
  `.venv/bin/python -m pytest -q tests/repo_quality/tools/test_lint_imports_phase3.py::test_arch004_admits_exact_fabric_world_facade_and_rejects_descendant tests/repo_quality/tools/test_architecture_phase3.py::test_fabric_world_exact_facade_is_shared_by_release_deep_import_classifier tests/repo_quality/architecture/test_fabric_world_write_waist.py::test_production_modules_use_the_fabric_world_write_waist`
  — exit 0, three selected cases passed.
- Exact append-only prose:
  “2026-08-31 round-2 supersession — **closed**. ARCH004 and the release collector now
  derive one definition: exactly `polisyos.fabric.world` is public and descendants remain
  private. Both owner contracts expose only the four already curated Runtime-used write
  identities. The synchronized baseline changed by exactly 12 deletions and zero
  additions, all newly exact-facade edges. The Phase-0 witness is intact,
  `create_world_snapshot` is not exported, `.store` remains rejected, and no exception
  was added.”

### `core-observability-canonical-interface-contract-drift` — blocked

- Verdict: `blocked`.
- `blocked_by`: IR/Core/Foundry/Architecture owner adjudication for the truthfulness
  family: whether its ten IR-owned identities project through Core observability or the
  nine Foundry consumers route through an admitted IR facade.
- Deciding command/predicate:
  `.venv/bin/python -m pytest -q tests/repo_quality/architecture/test_import_governance_contract.py::test_observability_deep_import_residual_is_exact_truthfulness_adjudication`
  — exit 0; the closure counterfactual directly calls
  `_cross_package_deep_imports({'polisyos.core.observability'})` and exits 0 only after
  asserting the returned canonical list contains exactly 11 rows. Thus the actual
  closed-interface predicate is nonempty and would fail.
- Exact append-only prose:
  “2026-08-31 round-2 supersession — **blocked by the truthfulness owner adjudication**.
  Every ruled mechanical move is complete: 173 Python statements across 172 files plus
  the `.pyi` companion. The exact remainder is 11 truthfulness statements in nine files,
  25 name occurrences, and ten unique names. Removing the deferred marker now makes the
  closed-interface exact-facade gate return those 11 rows rather than empty, so the marker
  remains and no premature public contract entry was added. Closure awaits only the
  named routing/ownership decision, after which those eleven move and contract/inventory
  reconciliation can execute. The Fabric relocation-owned adapter was untouched.”

### `import-policy-governance-runtime-corpus-dependency` — blocked

- Verdict: `blocked`.
- `blocked_by`: appointment of a Corpus package owner.
- Deciding command/predicate:
  `.venv/bin/python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml`
  — exit 1 with exactly one violation:
  `src/polisyos/runtime/http/services/governed_projection_validation_worker.py:560 [ARCH001] forbidden internal import: runtime -> corpus via polisyos.corpus (allowed={berl, common, core, data_forge, data_requirement, evidence, fabric, foundry, ir, lex, method_requirement, participation_requirement, pdc, runtime, scholar, scholar_requirement, scientist})`.
  Canonical complete Runtime census remains one statement / one file / two symbols,
  SHA-256 `63eef5900390a25b77e1c302c78ef72b14b70049c9ab42e9dbfa81430e130fcb`.
- Exact append-only prose:
  “2026-08-31 round-2 supersession — **blocked only by appointment of a Corpus package
  owner; direction ruled**. Runtime -> Corpus remains forbidden. The complete dependency
  is one deferred statement in one Runtime worker importing two fixture-loader symbols.
  Under §9 item 5 the missing owner binds the claim, never the capability; no allowance
  or exception was created.”

### `ds18-continuous-incident-monitors-static-cycle` — closed

- Verdict: `closed`.
- Deciding command/predicate:
  `.venv/bin/python -m pytest -q tests/repo_quality/architecture/test_continuous_incident_import_cycle.py::test_incident_monitor_bridge_removes_exactly_its_static_scc tests/repo_quality/architecture/test_continuous_incident_import_cycle.py::test_incident_owner_persists_content_bound_monitor_event`
  — exit 0, two selected cases passed. The canonical sorted SCC set is 15 tuples versus
  16 at base; subtraction is exactly the Incident/Monitors tuple, additions are empty,
  and the other three finding tuples are byte-identical.
- Exact append-only prose:
  “2026-08-31 round-2 supersession — **closed**. The incident-specific persistence bridge
  remains in the Incident owner. Canonical SCC set comparison removes exactly the
  Incident/Monitors tuple, adds none, and leaves the other three finding tuples
  byte-identical; the finding measure is three rather than four. No cycle predicate,
  registry, exception, or witness changed.”

## 2026-08-31 — round 3 admission

Starting state re-read from the attached branch: `codex/debt-f-architecture-imports` at
`2e8105a28001ecabd561e023accfb6e9c17738e9`, clean and 14 commits ahead of the slice
base. The architect accepted the four structural closures and supplied three
supersessions:

1. Identity decision §9 item 6 separates an appointment to perform an act from neutral
   vocabulary describing it. The EvalSafety split can therefore keep every minting act
   in Runtime while moving vocabulary, verifier shape, produced markers, and pure
   verification into PDC.
2. `core/observability/truthfulness.py` names itself as an IR-owned compatibility export,
   while `ir/analytics/_truthfulness.py` is the implementation and the IR facade already
   exports the complete family. The alleged ownership decision was present in the
   artifact.
3. The Runtime/Corpus edge repeats a legacy denominator against committed test fixtures.
   Its executability turns on a behavioral measurement: whether the production projector
   rejects a non-13 source before the owner worker runs.

No import exception, witness deletion, public-symbol laundering, gate weakening, task A
file, or architect-owned register file is in scope. Round-3 work proceeds serially by
row, with red-first behavioral tests and complete structural censuses.

### Runtime / Corpus — live-path measurement and repair

The denominator assertion is dead in the worker. A behavioral counterfactual copied the
complete proving-ground source, removed one manifest row (12 fixture identities/cases),
and trapped `_run_owner_validation`. The real `GovernedProjectionService` returned
`availability=invalid_source`, validation `status=not_run`, issue
`projection_contract_invalid`, and the trap recorded **zero owner-validator calls**. The
canonical denominator predicate is therefore `_project_proving_ground` over the composite
source's identity and record sequences; the worker's later Corpus re-load could never
adjudicate a disagreement.

Red-first node:
`tests/repo_quality/architecture/test_import_governance_contract.py::test_runtime_corpus_edge_is_replaced_by_live_projection_denominator`
failed on the sole Runtime -> Corpus AST row. After removing only the duplicate re-load,
the same node exits 0, the canonical worker-source parameter cases exit 0 (two selected
cases), and the full import gate exits 0 with zero lapsed covers, zero unadjudicated
violations, and zero allowed exceptions. The worker continues to verify all component
hashes before and after owner validation and content-binds the projected payload into its
semantic receipt.

### Scientist / Runtime — §9 item 6 execution

The seven residual statements were one contract but two kinds of thing. Five
TYPE_CHECKING statements now import `EvalSafetyVerifierPort` and
`EvaluationExecutionContext` from PDC. The two module-level consumers now import the
consumer-minted `EvalSafetyAdmissionChallenge` and pure receipt verifier from PDC. Both
removed their Runtime `resolve_evaluation_mode` call and read
`context.mode_resolution`, a non-serialized deterministic projection of the already
validated canonical `context.evaluation_mode`; the execution-context hash therefore did
not change. Runtime still owns token parsing and every decision, certificate, revision,
pack-admission, and consumer-receipt minting act.

The first implementation attempt correctly failed the full import gate with exactly one
new ARCH006 diagnostic:
`src/polisyos/runtime/quality/evaluation_safety.py:38 [ARCH006] forbidden internal
subpackage import: polisyos.runtime.quality.evaluation_safety ->
polisyos.pdc._impl.evaluation_safety. Cross-root imports must go through public facades.`
The gate was not weakened and no exception was added. The final seal has PDC own the
private producer token and exact Runtime-subtype registry. Runtime defines the one
private minting subtype through the public base contract; PDC fails closed until that
exact type is registered and checks exact type, token, canonical fingerprint, status,
context hash, challenge, consumer, intake, certificate, and revision head.

Falsifier: a hand-constructed `EvalSafetyConsumerAdmissionReceipt` with `verified`
status, no blockers, and every context/challenge/certificate/revision field made exact
returns `False`. The real Runtime CAS-backed verifier test mints the registered subtype
and returns `True`; replayed context and challenge variants still return `False`.

Post-move canon is a complete `Path.rglob("*.py")` AST walk. Each structural row contains
source-relative path, source module, exact target-module sequence, ordered
`{name,asname}` aliases, and structural scope; rows sort by compact sorted-key JSON and
the compact JSON array has no trailing newline. Line number is deliberately excluded.

- Scientist -> Runtime: 585 Python files / **zero import statements / zero aliases /
  zero importing files**, canonical two-byte `[]` SHA-256
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- Runtime -> Scientist: 280 Python files / 70 import statements / 110 aliases / 28
  importing files; 34 module, zero class, 36 deferred; structural canonical SHA-256
  `c57785431914251ffe2044ed7fa37bd3f1d939bd31aef53eab4a41e8706d10de` over
  20,342 bytes.

The `scientist` direction row no longer admits `runtime`; the full v2 import gate exits
0 with zero violations and zero allowed exceptions, and its reported package-level SCC
set no longer contains Runtime. Five focused closure/facade/Scientist consumer nodes and
the real Runtime minting node exit 0. Neither `generation_cycle.py` nor
`promotion_sequence.py` was touched.

Scientist paths touched in this migration:

1. `src/polisyos/scientist/api.py`
2. `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py`
3. `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`
4. `src/polisyos/scientist/orchestration/engine/context.py`
5. `src/polisyos/scientist/orchestration/workflows/builder.py`

PDC paths touched in this migration:

1. `src/polisyos/pdc/__init__.py`
2. `src/polisyos/pdc/_impl/evaluation_safety.py`

### Core observability — IR-owned truthfulness completion

The alleged adjudication was already encoded in the artifact: the 29-line Core module
calls itself a compatibility export for IR-owned truthfulness contracts, while
`src/polisyos/ir/analytics/_truthfulness.py` owns the implementation and the lazy
`polisyos.ir.analytics` facade resolves all ten names. The eleven production statements
in nine Foundry files were therefore re-spelled onto that exact IR facade; no symbol was
promoted merely to satisfy a linter.

The red-first closure nodes first reported the exact eleven deep rows, the missing Core
observability contract entry, and the same eleven rows when the deferred marker was
removed. After the move, the five selected closure cases exit 0. Executing the four
focused truthfulness consumer files adds 78 passing cases. A complete AST walk of the
current `src/polisyos` tree examines 2,619 source files (2,614 `.py` plus five `.pyi`):
the cross-package Core-observability corpus is 238 exact-facade statements / 280 imported
aliases / 216 importing files and **zero deep statements / zero deep aliases / zero deep
files**. The closure property is the empty deep-row canonical set, not a comparison of
the old and new statement totals.

The deprecated Core truthfulness alias remains because six consumers are outside this
round's writable production set. A complete `git ls-files '*.py'` AST walk over 5,712
tracked Python files measures eight alias imports / 22 imported aliases / six files:

1. `src/polisyos/core/contracts/execution_plan.py` — one same-package statement, five aliases;
2. `tools/quality/validation/check_layer3_gy_value_gate_contract.py` — one statement, three aliases;
3. `tests/unit/foundry/methods/catalog/bayesian/test_methods.py` — two statements, three aliases;
4. `tests/unit/foundry/methods/test_truthfulness_protocol.py` — two statements, five aliases;
5. `tests/unit/foundry/methods/test_value_evidence.py` — one statement, three aliases; and
6. `tests/unit/ir/analytics/test_simulation_proof_bridge.py` — one statement, three aliases.

The alias now carries an explicit deprecation marker and warning directing new consumers
to `polisyos.ir.analytics`; none of these bounded compatibility consumers is a
cross-package production deep edge. `polisyos.core.observability` was removed from
`DEFERRED_PUBLIC_CANONICAL_INTERFACES`, and only the two exact facades used by the final
architecture (`polisyos.core.observability` and `polisyos.ir.analytics`) were added to
their package and aggregate public-surface contracts.

Owner synchronization removed 226 canonical deep-import baseline edges and added none:
215 former exact Core-observability source-module edges, nine truthfulness source-module
edges, and two pre-existing IR-analytics source-module edges are now supported-facade
traffic. `uv run polisyos-tools architecture guardrails sync` exits 0, and the matching
`guardrails check --skip-generated-checks` exits 0. The full generated-freshness variant
exits 1 only at the unrelated trust-claim-posture probe because its ratified identity
basis differs from the admitted closed receipt; import and public-surface guardrails are
already green. The full version-2 import scan exits 0 with zero lapsed covers, zero
unadjudicated violations, and zero allowed exceptions. The Fabric observability adapter
was not touched.

### Closeout correction — direct marker construction

The independent P32 closeout probe found one same-class escape after the first
Scientist/Runtime commit: directly constructing Runtime's private produced-receipt
subtype auto-sealed it in PDC's `model_post_init`, so the stronger marker-level forgery
was accepted even though construction of the public base receipt was rejected. The new
probe failed before repair with the exact assertion that both hand-constructed receipts
must be rejected.

The correction completes the relocation the ruling named. PDC now owns the private
`_ProducedEvalSafetyConsumerAdmissionReceipt` marker, producer token, fingerprint check,
and pure verifier. The marker is facade-bound only for Runtime's internal exact-facade
import and remains absent from PDC's public `__all__`. Construction alone never seals a
receipt. Runtime invokes the marker's private `_mark_produced()` only after its complete
current-state verification finishes with no blockers. Both direct public-base and direct
marker construction now return `False`; the real Runtime CAS-backed mint returns `True`.
This append supersedes the earlier description of an auto-registering Runtime subtype;
no gate, policy permission, exception, public facade contract, or appointment changed.

### Round-3 lane-A gate overlay

Task A advanced during closeout. The final measurement archives Task F source commit
`8802caae0b3f8f080f90e03e5c03e471ce7262ad`, overlays all seven task-A changed paths from
`60bbb0531787588ca93c31042483b4515e09a60a` (four Python files, two under `src/polisyos`),
and runs the full import scan. Exit is 0: policy version 2 loads, the complete root
coverage register loads, no A path emits ARCH007, the scan has zero lapsed covers and
zero unadjudicated violations, and no exception is consumed. Therefore ARCH007,
contract-v2 loading, and root coverage are all green for the measured A head.

### Complete Scientist and PDC merge surface

Task B's later merge must reconcile the complete base-to-final source-path set, not only
the five files in the last EvalSafety residual.

PDC paths (three):

1. `src/polisyos/pdc/__init__.py`
2. `src/polisyos/pdc/_impl/evaluation_safety.py`
3. `src/polisyos/pdc/_impl/world_model_record.py`

Scientist paths (20):

1. `src/polisyos/scientist/api.py`
2. `src/polisyos/scientist/artifacts/decision_compiler.py`
3. `src/polisyos/scientist/governance/continuous/incident.py`
4. `src/polisyos/scientist/governance/continuous/monitors.py`
5. `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py`
6. `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`
7. `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py`
8. `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`
9. `src/polisyos/scientist/orchestration/engine/context.py`
10. `src/polisyos/scientist/orchestration/engine/runner/_activity_worker.py`
11. `src/polisyos/scientist/orchestration/engine/runner/ray_runner.py`
12. `src/polisyos/scientist/orchestration/engine/runner/temporal_runner.py`
13. `src/polisyos/scientist/orchestration/llm/budget_enforcer.py`
14. `src/polisyos/scientist/orchestration/workflows/builder.py`
15. `src/polisyos/scientist/replay/AUTHORING.md`
16. `src/polisyos/scientist/replay/README.md`
17. `src/polisyos/scientist/replay/backend.py`
18. `src/polisyos/scientist/replay/deterministic.py`
19. `src/polisyos/scientist/replay/verification.py`
20. `src/polisyos/scientist/validation/decision_artifact_quality.py`

## Register closure dossier — round-3 supersession

Arithmetic: **3 remaining rows = 3 closed + 0 blocked**. The complete Task F set is
**7 rows = 7 closed + 0 blocked** (core: **5 = 5 closed + 0 blocked**; adjacent:
**2 = 2 closed + 0 blocked**).

### `scientist-runtime-declared-cycle` — closed

- Verdict: `closed`.
- Deciding command/predicate: the exact combined closure wave including
  `test_scientist_runtime_declared_cycle_is_removed_after_eval_safety_split`,
  `test_pdc_eval_safety_verifier_rejects_hand_constructed_receipt`, the real CAS-backed
  Runtime mint, and both Scientist consumer cases exits 0 (14 selected cases in the
  combined wave). A fresh complete AST walk exits 0 over 585 Scientist Python files with
  zero Runtime statements, zero imported aliases, and zero importing files. The full
  version-2 import scan exits 0 with no Runtime/Scientist SCC and no exception.
- Exact append-only prose:
  “2026-08-31 round-3 supersession — **closed**. Identity decision §9 item 6 leaves every
  EvalSafety minting act under Runtime while neutral vocabulary, the produced marker,
  verifier port, execution context, consumer challenge, and pure verification live in
  PDC. Runtime resolves mode while constructing the context; Scientist reads the
  deterministic `mode_resolution` projection. The complete 585-file Scientist AST canon
  is zero Runtime statements / zero aliases / zero importing files, so the reverse
  permission and declared cycle are gone. Hand construction of either the public receipt
  or its private produced marker fails verification; the real Runtime-sealed receipt
  passes. No appointment, exception, or witness was changed.”

### `core-observability-canonical-interface-contract-drift` — closed

- Verdict: `closed`.
- Deciding command/predicate: the five selected exact facade/deferred-interface cases
  exit 0; 78 focused truthfulness consumer cases exit 0; and
  `uv run polisyos-tools architecture guardrails check --skip-generated-checks` exits 0.
  The complete current `src/polisyos` AST denominator is 2,619 files (2,614 `.py` plus
  five `.pyi`) with 238 exact Core-observability statements and zero cross-package deep
  statements. The compatibility census over 5,712 tracked `.py` files is eight statements
  / 22 aliases / six files, all explicitly bounded outside cross-package production use.
- Exact append-only prose:
  “2026-08-31 round-3 supersession — **closed**. The shim itself declares IR ownership,
  and the existing `polisyos.ir.analytics` facade resolves all ten truthfulness names.
  Eleven production statements in nine Foundry files now use that exact facade. The
  complete closed-interface canon contains zero cross-package deep Core-observability
  statements; `polisyos.core.observability` is no longer deferred and the exact Core and
  IR facades are synchronized through package, aggregate contract, inventory, reference,
  and deep-import baseline owners. The old Core truthfulness alias remains only as an
  explicit deprecated compatibility route for eight statements / 22 aliases / six files:
  one same-package Core consumer, one repository tool, and four test files. The Fabric
  adapter was untouched; no exception was added or renewed.”

### `import-policy-governance-runtime-corpus-dependency` — closed

- Verdict: `closed`.
- Deciding command/predicate:
  `test_runtime_corpus_edge_is_replaced_by_live_projection_denominator` and both canonical
  owner-source parameter cases are included in the 14-case exact wave, which exits 0. A
  12-row copied source makes the real service return `invalid_source`, validation
  `not_run`, issue `projection_contract_invalid`, and zero owner-worker calls. A fresh
  complete Runtime AST walk exits 0 over 280 Python files with zero Corpus statements,
  zero imported aliases, and zero importing files; the full import gate exits 0.
- Exact append-only prose:
  “2026-08-31 round-3 supersession — **closed**. The production projector already owns
  the exact 13-identity/13-record proving-ground denominator: a 12-row source fails as
  `projection_contract_invalid` before the owner worker runs, with zero worker calls.
  The later `legacy_proving_ground_denominator_mismatch` fixture re-load was therefore
  dead and has been removed without replacing it with a test-shaped production artifact.
  The complete 280-file Runtime AST canon is zero Corpus statements / zero aliases / zero
  importing files. Runtime remains forbidden from importing Corpus; no direction,
  package-owner exception, or import exception was created.”
