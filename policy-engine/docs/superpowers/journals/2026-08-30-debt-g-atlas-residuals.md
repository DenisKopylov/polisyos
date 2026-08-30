# Debt G — Atlas Residuals Execution Journal

Date: 2026-08-30  
Branch: `codex/debt-g-atlas-residuals`  
Base: `784d02014`  
Plan: `docs/superpowers/plans/2026-08-30-debt-g-atlas-residuals.md`

## Scope and preservation

This lane owns eleven residual rows and may not edit the debt register, generated
ledger, Atlas master plan, GY plan, or published debt denominator. Under the runtime
dashboard it owns only `scripts/persist_atlas_evidence.py`; task D retains all app
source and the frontend-disposition test module. Corrections append. Routing is
never treated as ownership.

## Pattern pre-pass

Relevant register patterns are P01/P02 (contract or routing without a real bridge),
P03 (hidden DS18 richness), P29/P32 (marker or form as proof), P35/P36 (sampled
denominator and authority by adjacency), P37/P38 (declared/proxy gate predicates),
P39 (mandatory companions), P40 (same-class ladder repair), and P41 (red
provenance). The target pattern is a live enforcement bridge, a Git/content-bound
historical mapping, an independently replayed DS18 predicate, and append-only
argument evidence.

## Initial complete-row read

All eleven primary register rows were read in full before planning. The later
append-only occurrences of `ds4-waist-decision-grade` were also read. The initial
capability states are not collapsed: DS4 is still `surface_missing`; the three
DS8 scope rows are `absent/unallocated`; DS6 has an established TypeScript producer
but a stale Python admission projection; the timing row is
`verification_missing`; the two task-C overlaps keep producer and Atlas-scope
halves separate.

## Measurements before implementation

### Frontend baseline bindings

The canonical current field is `lint.resolution_content_bindings`, validated by
`architecture/atlas_surfaces/check_frontend_disposition_register.py`; the older
`resolutions[].origin_identity.source_content_sha256` coordinate still exists in
75/75 resolution rows but is not the current content-binding field. A complete
direct walk found 46 binding rows over 45 unique paths: 2 `.cjs`, 14 `.ts`, and 30
`.tsx` binding rows, with zero current SHA-256 mismatches. All six paths named by
the debt row are fresh. A full checker invocation was an environment non-receipt
before `uv sync` because `jsonschema>=4.25` was absent; it is not used as the
binding verdict.

### DS5 successor table

The complete `DS5-enforcement-waist.md` handoff table contains 27 groups over 58
sites. The six historical handoffs comprise 6 groups/11 sites: DS12 3/7, DS14 1/1,
DS15 1/1, and DS18 1/2. Current planless successors are DS12 3 groups/7 sites and
DS14 1/1: 4 groups/8 sites. DS15 1/1 and DS18 1/2 now have standalone plans but the
exact group labels are not absorbed into their plan text.

### Generated DecisionGrade

The PDC owner still declares `DecisionGrade`, while the OpenAPI and generated
clients carry inline four-value enums/unions. Across the two registered generated
artifact families and their six outputs there are zero named `DecisionGrade` alias
occurrences. The next-regeneration swap has not happened.

### Timing workload identity

The requested single pytest node failed before repair at `67 == 232`: 191
source-declared tests in `test_frontend_disposition_register.py` plus 41 in
`test_status_retirement_inventory.py`. A real current pytest collection is a
different canonical form: 194 + 41 = 235 runnable node IDs, SHA-256
`ede7f43cb4f88b325950e5a958eb0efc7050837717038404a816987f3279fab3` for the
newline-joined ordered IDs. The register separately preserves 181, 190, and 210.
These are one workload-identity defect, not candidate totals to choose among.

At publication commit `6bcc95bff32645189ff2ed65a719c7990e48c52a`, the two
historical test blobs expose 30 + 37 = 67 source-declared unittest node IDs. The
binding repair will attach the receipt to that complete ordered historical mapping
and its Git source, not to today's population.

### DS18 projection

The current register contains 621 production TypeScript files and 759 render/export
roots. It classifies 126 roots as decision-bearing or inherited and covers all 126;
every file/root predicate provenance is `independently_reconciled`, and a direct
content walk found zero file SHA-256 mismatches. The older 605/719/77/77 and
616/733/94/94 receipts are dated source freezes, not current totals. The Python
persistence adapter alone still hard-codes primitive adoption as unknown.

## Rulings

- Ruling: the detailed task brief is the approved design constraint for this
  maintenance lane; no separate brainstorming approval pause is needed. Cost if
  wrong: the user may prefer a different manifest surface and the small mechanism
  would need rework.
- Ruling: all three DS8 obligations are inputs to each of DS12, DS13, and DS14
  scope setting. The gate demands the complete three-row input set from every one
  of those target plans. Cost if wrong: a later plan may carry redundant input
  acknowledgements, but no row will be falsely closed.
- Ruling: the timing sample is historical. Bind its immutable publication snapshot
  and exact node map; do not mutate a completed duration to follow current test
  growth. Cost if wrong: the architect may instead require a fresh timed sample,
  in which case the historical mapping remains valid evidence but the catalog
  needs a new owner-controlled sample.

## Execution ledger

Implementation and review receipts append below. The final section of this file is
reserved for the eleven-block Register closure dossier.

### Task 1 — DS8 residual scope-obligation gate

Implemented a strict `slice-scope-obligations` manifest and schema, then wired a
live validator into `check_atlas_enforcement.py`. The manifest is the sole
enumeration of the three DS8 residual IDs; it explicitly makes acknowledgements
`candidate_only` with `closure_effect: none`. The validator walks every tracked
Markdown plan, parses complete YAML frontmatter, identifies a target only by
`type: slice-plan` plus `slice`, and requires the exact unique
`atlas_residual_inputs` set. Missing DS12/DS13/DS14 plans remain open and green;
multiple plans for a target fail.

RED receipt: after the focused environment setup, the five new unittest nodes
failed with `AttributeError` because `validate_slice_scope_obligations` and
`_tracked_atlas_plan_paths` did not yet exist. The first collection attempt was
an environment non-receipt (`ModuleNotFoundError: jsonschema`); the authorized
locked setup was `uv sync --frozen --extra test`.

GREEN receipt: the same five focused nodes passed (`Ran 5 tests ... OK`). The
live `uv run python architecture/atlas_surfaces/check_atlas_enforcement.py
--check` completed with exit 1 from unrelated Atlas inventory/authority,
source-denominator, query-cache, status, and architecture-graph checks; their
provenance was not re-established in this task. It emitted no
`slice_scope_obligation_*` error. One accidental non-PTY duplicate checker process
was terminated, leaving one PTY-backed authoritative receipt.

### Task 2 — historical Atlas timing workload identity

The pre-repair focused node was red: the completed receipt's `67` tests passed
count was compared to the current helper-derived AST count, `191 + 41 = 232`.
This is distinct from the inherited register derivations `181`, `190`, and `210`,
and from current pytest collection, `194 + 41 = 235` node IDs. The current forms
evidence growth; none selects a replacement count for the historical sample.

The repaired test resolves the publication commit
`6bcc95bff32645189ff2ed65a719c7990e48c52a`, reads precisely the two paths named
by the catalog command, and derives their ordered pytest node IDs from supported
unittest forms. It content-binds the historical frontend blob to
`841466263c618a3142a6d5327c72072ad0e95bf4d738516f6d240eb98601b685` (30 IDs),
the status blob to
`7f5418b7e809b1f1bac0470ecc2a553c878b14d886ea39494362067908e7ca0f` (37 IDs),
and compact canonical JSON of their complete ordered 67-string map to
`9b08f0ed2e74bf888009820529e2901c6dd3bedb40bf55a679a362efaf12aea6`. It rejects
duplicate node IDs and decorated forms whose runnable cardinality cannot be
derived exactly. The cited receipt remains `67` tests passed.

RED receipt:
`uv run --extra test --with 'jsonschema>=4.25' python -m pytest tests/repo_quality/tools/test_timing.py::test_atlas_python_governance_lane_names_one_exact_runnable_workload -q`
exited 1 with `AssertionError: assert 67 == 232`. The new test expectation then
failed with the expected missing-helper `NameError` before implementation.

GREEN receipt:
`uv run --extra test --with 'jsonschema>=4.25' python -m pytest tests/repo_quality/tools/test_timing.py::test_atlas_python_governance_lane_names_one_exact_runnable_workload`
exited 0: `1 passed in 0.13s`.

### Task 3 — DS6 Python admission of the DS18 projection

The pre-repair four-node Vitest selector had two failures and two passes. The
read-only current-measurement node expected the dated `94/94` freeze but observed
the current `126/126`; the persistence node failed because Python still projected
primitive adoption from the DS1 readiness population as `unknown`. A direct
persistence invocation confirmed the owned failure as `health-metric rows do not
bind the recomputed canonical-source projection`.

Mechanism commit: `2d35c2e71` (`fix(atlas): admit live DS18 health projection`).

The Python admission adapter now invokes the canonical DS18 checker through the
repository `.venv/bin/python -I` with the fixed minimal child environment and the
resolved allowlisted Node 22 executable from `_trusted_node`. It admits exactly
five fields, requires `predicate_provenance: independently_reconciled`, positive
integer counts, and `covered_root_count == obligated_root_count`; it derives the
measured row without storing any current count in code. The row content-binds the
register, schema, checker, and AST scanner. Checker rejection, duplicate or
malformed JSON, extra fields, wrong provenance, boolean/non-positive counts, and
incomplete coverage all produce an exact bounded reason and retain
`unknown` / `not_established` with zero known facts. The shared source-projection
signature was updated for both health and readiness; the readiness reconciler's
five-value interface replayed successfully. An already-landed producer wording
change (`Six` to `Seven` source proxies) was mirrored in the owned Python adapter
because it otherwise independently blocked the persistence node.

GREEN receipts: the canonical fixed-environment checker exited 0 with 621
production files, 759 roots, and 126/126 covered obligated roots. Direct Core CAS
persistence exited 0 with a measured 126/126 primitive row, the same three current
facts, `predicate_provenance: recomputed`, and four DS18 basis refs. The exact
persistence Vitest node passed (`1 passed | 22 skipped`); the exact caller `PATH`
and `NODE_OPTIONS` nodes passed (`2 passed | 21 skipped`); Ruff, byte compilation,
and `git diff --check` passed. The final four-node selector had three passes and
one task-D-owned read-only failure: the current-measurement node still expects
`94/94` while the producer correctly emits `126/126`. No TypeScript source or test
was changed.

Pattern closeout: P03's hidden DS18 richness is now consumed by the existing
persistence bridge; P29/P32 are met by replay and content refs rather than marker
presence; P37 fails closed unless the checker itself establishes the independent
predicate; P38 measures the obligated-root relation rather than a stored count.
The owned Python predicate is green. The remaining task-D literal expectation is
the recorded P41 handoff, not a reason to substitute another frozen total.

#### Task 3 independent-review correction

Review found that commit `2d35c2e71` had changed the shared
`_health_source_projection()` helper from its established no-argument two-tuple
contract to a required-argument three-tuple. The exact readiness admission witness
failed with `TypeError: _health_source_projection() missing 1 required positional
argument: 'node_executable'`. Commit `5babf54d0` restores that interface exactly.
Readiness again consumes only the canonical health-source projection and does not
run DS18. The health path invokes DS18 separately and overlaps that independent
replay with the fixed TypeScript producer; their reports are still compared before
admission, so disagreement continues to reject rather than widen authority.

The same repair replaces unbounded checker capture with a selector-driven process
reader capped at 8 MiB independently for stdout and stderr, matching the producer's
`maxBuffer`. More than 8 MiB on either stream kills the checker and yields a
77-character bounded reason. Ordinary nonzero stderr is copied into a limitation
only through a 2,048-byte excerpt; a 3,000-byte witness produced a 2,151-character
reason with an explicit truncation suffix. Real-process witnesses for stdout
overflow, stderr overflow, bounded ordinary failure, and a small ordinary failure
all passed.

The earlier journal wording that zero-exit malformed checker output was proven to
persist as unknown is retracted. Python parses such output tolerantly at its helper
boundary, but the canonical TypeScript producer currently performs `JSON.parse`
and strict projection parsing without a tolerant catch; persistent zero-exit
malformed output therefore terminates the producer before Python can admit a row.
That behavior is task D's exact source handoff in
`runDs18TimeSemanticsCoverageValidator`: if persisted unknown is required for this
case, task D must convert JSON/schema parse rejection into the same bounded
`kind: not_established` result. Task G did not fabricate a producer report or edit
the task-D source.

The actual nonzero checker path was exercised end to end by temporarily changing
only the register's `covered_root_count` from 126 to 0, invoking the real producer
and persistence operation, and restoring the exact original bytes in `finally`.
Persistence exited 0 with `unknown / not_established`, zero known facts, and the
bounded limitation prefix
`ds18_time_semantics_count_drift:covered_root_count`. The restored register digest
was `c2893870139f3eae5042e54ba23a1692c10680f1ec0dc404cd3d879efe01544f`, and the
post-witness Git diff was empty for the register. The exact red-denominator Vitest
node separately passed the unknown-row schema contract.

Final focused receipts after the correction: the exact readiness witness passed
(`1 passed | 32 skipped`, 13.44 s); exact persistence plus red-denominator nodes
passed (`2 passed | 21 skipped`, 7.80 s); exact caller `PATH` and `NODE_OPTIONS`
nodes passed under the default 15-second ceiling (`2 passed | 21 skipped`,
12.96 s). The canonical checker remained 621 files / 759 roots / 126/126 at
`independently_reconciled`; Ruff, byte compilation, and `git diff --check` passed.
The separate task-D `94/94` current-measurement expectation remains the only known
focused read-only red.
