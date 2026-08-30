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
