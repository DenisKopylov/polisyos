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
