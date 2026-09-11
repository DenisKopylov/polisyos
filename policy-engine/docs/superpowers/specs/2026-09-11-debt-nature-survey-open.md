# Debt nature survey — open workstream

Base `fc823071a7b6f2c9a573172aec3499ad6d138c0f`. The exact denominator is the 27 open
IDs in the reconciled main survey. This document characterizes claims; it changes no
standing. The register and ledger are not evidence about the tree.

Commands run from `policy-engine/`. Borrowed Python is explicitly named in commands;
imports in behavioral receipts bind to this worktree's source. Offline local bootstrap
failed on uncached `jaxlib==0.8.2`; this is an environment nonreceipt. No dependency or
source was altered to make a probe pass. Every count below names its own denominator.
Raw outputs are under `docs/superpowers/journals/debt-survey/open/raw/`; their hashes
and exact commands are retained in the workstream receipt index.

The common AST instrument walks the entire pinned `src/`, `tests/`, `tools/` and
`architecture/` Python sets: Git-tree and independent filesystem identities agree;
`ast.walk` and `NodeVisitor` agree on definitions/classes/calls, including async.
There are 5,686 Python files, of which 2,653 are in `src/`, with no parse ambiguities.
The full path denominator is enumerated in `raw/python-denominator.json`. Calls are
syntactic occurrences; they are not automatically dynamic reachability proof.

## `pyproject-exceeds-its-declared-line-budget`

**Measured:** the actual registered gate returns exit **1 / FAILED**, complete
coverage, **307 physical lines / one `pyproject.toml`**, ceiling 300. The historical
305-line premise is stale. The mechanism now explicitly says it counts comments and
blank lines and does not measure configuration complexity, dependency correctness,
resolver cost or TOML validity. Evidence: `pyproject.toml@fc823071a` and
`tools/quality/validation/repository_structure_phase0.py@fc823071a`.

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.cli validation repository-structure-phase0 gate --gate pyproject_size --json
```

Full output: `raw/pyproject-gate.json`. **Narrower:** the warning is a bounded physical
size fact, not a demonstrated semantic-maintainability defect. **Wider:** no wider
manifest population follows from this single-file gate. **Reduction/class:** no shared
deciding property with dependency correctness, source-schema unreadability or invocation
coverage is established. A shared DevX holder would not make those one debt. Unblocking
an edit and discharging the unchanged size predicate are distinct; neither was done.
**Unestablished:** the maintainability effect of any particular extraction and historical
attribution of the excess; no historical replay is claimed.

## `stale-worktree-registrations-collide-with-new-lane-names`

**Measured, current shared Git state rather than pinned source:** Git porcelain and
independent `.git/worktrees/*/gitdir` records agree on linked-path identities. There are
**78 registrations / the complete current registration set**, including this survey;
**53 paths are absent**. The row's 72 denominator has decayed; the missing-directory
count has not. The supplied pre-survey 77 becomes 78 after this worktree is added.

```sh
python3 docs/superpowers/journals/debt-survey/open/probes.py worktrees
```

Full output: `raw/worktrees.json`. **Narrower:** no loss of branch objects or source is
proved by missing directories. **Wider:** commissioning has two independently checked
names, a branch and a registered path; missing-directory cleanup alone says nothing
about branch-name reuse. **Reduction/class:** allocation failure in other debt rows is
not this shared Git-registration mechanism. Here availability of two names unblocks
commissioning; discharging accumulated registrations and the prompt preflight property
are separate predicates. **Unestablished:** the row's historical 43 merged-branch count
and universal compliance by future prompts. No registration was pruned.

## `calibration-report-fixture-blanket-fields`

**Measured:** the complete exact-kind AST population in
`tests/_helpers/runtime_http.py@fc823071a` has **one calibration-report writer call**,
at line 398, through `_put_json`. Executing the actual helper adds three keys:
`authority_boundary`, `authority_result`, `legacy_path_disposition`. All three are
outside the actual **15-field** `CalibrationReport` model in
`src/polisyos/foundry/calibration/report.py@fc823071a`; its `extra="forbid"` admission
rejects each as `extra_forbidden`. The unmodified payload is accepted when the separate
version-pattern field is omitted from both variants.

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py calibration
```

Full output: `raw/calibration.json`. **Narrower:** the strict producer does not silently
ignore these fields; the fixture bypasses that strict shape using a generic mapping
writer. **Wider, inferred:** `_with_runtime_fixture_authority` acts on any mapping that
lacks `authority_boundary`, so the mechanism is broader than the one artifact kind.
Which other kinds violate their own schemas is unestablished and is not a new row.
**Reduction/class:** shared fixture decoration is the candidate mechanism; a common
three-key shape is not proof that every decorated artifact is invalid. No pair reduction
is established. Availability of the typed serializer is an enabling fact; discharge
would be the actual persisted fixture agreeing with its producer, not changing a label.
**Unestablished:** full HTTP fixture persistence/replay and every other kind's validity.

## `foundry-requirements-flat-manifest-consumer-unmeasured`

**Measured:** executing the actual Runtime helper with a declared three-input contrast
(absent manifest / flat matching manifest / flat nonmatching construct) yields
`fail / pass / fail`, and the matching case emits `runtime_consistent`, fabricated
`gate://`, `uncertainty:`, `limitation:` and `method-result:` references from the target
name. The complete returned reports are retained. Evidence:
`src/polisyos/runtime/quality/producer_pipeline.py@fc823071a` and
`src/polisyos/foundry/methods/selection/requirements.py@fc823071a`.

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py requirements
```

Full output: `raw/requirements.json`. The complete 2,653-source-Python census locates
four direct calls to `select_method_candidates_for_requirements`: Foundry's method
report, Runtime's requirement pipeline, G2 method bindings and workspace recomputation.
Only a trace of their supplied arguments establishes manifest consumption; the mere
presence of those calls does not. Replays:

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/inspect_tree.py ast '(^|\.)(select_method_candidates_for_requirements|_method_candidates_from_capabilities|_manifest_rows)$' --source-only
```

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/inspect_tree.py ast '(^|\.)(_foundry_requirement_report|build_g2_method_requirement_bindings|build_foundry_method_report)$' --source-only
```

Full outputs: `raw/requirements-ast.json`, `raw/requirements-callers-ast.json`.
The actual helper's source parent is `run_requirement_spec_producer_pipeline`; this is
a source trace, not a replay of a served request. Existing selection tests also run
exit 0 over their complete four-test-function file:

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/foundry/methods/selection/test_method_requirements.py -q
```

**Narrower:** blanket `mechanism_unmeasured` no longer describes the helper boundary.
**Wider, inferred:** the predicate is manufacture of method-validity-looking evidence
from a manifest declaration, not simply a duplicate parser. **Reduction:** Ukraine's
unselected method contracts concern actual execution consumers; this concerns how a
selection report acquires its asserted evidence, so they are not established as one debt.
**Class:** potential shared input-owner/authority substitution, but common repair and
holder across those consumers are unestablished. A valid route owner could enable
admission; discharge requires the real consuming path to refuse false evidence.
**Unestablished:** full production input arrival, downstream authority effect and
equivalence to an existing canonical owner. No helper result is promoted to that claim.

## `udf-retained-source-schema-is-malformed-and-stays-ambiguous`

**Measured:** this is external retained data, not a malformed tracked source file.
The coordinate is supplied by finding **PR1-SA02** in
`docs/superpowers/journals/gy-phase5-evidence/pr1/stage3-scope-audit.md@fc823071a`;
fresh reading of that actual current file reproduces
`Expecting ',' delimiter: line 49 column 3 (char 1013)`. Its SHA-256 is
`a09bf61d5f4590bf98b7fbee6bf36968d734ce68a180b8c390de50125cf238a0`.

```sh
python3 docs/superpowers/journals/debt-survey/open/probes.py udf
```

Full output: `raw/udf.json`, enumerating the **7 direct `.json` siblings** in
`production_data/canonical/local_data_20260501/policy_engine_data/curated/`, with
glob/independent-iterdir identity equality: 6 readable, 1 ambiguous. Separately,
the complete **2,844 tracked `.json` files** in the product's pinned Git tree all parse;
the independent current-index identity set agrees after excluding only this survey's
added receipts:

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py json-readability
```

Full output: `raw/json-readability-reconciled.json`. **Narrower:** the location and exact
syntax failure are established; “every source is unreadable” is not. **Wider:** the
affected property is completeness of any *declared* population that includes this file;
its denominator may still be enumerated, but extraction from the unreadable member is
ambiguous. **Reduction/class:** no identity with the Lex API's absent-column defect is
established. They share a data-read prerequisite, not a demonstrated repair or holder.
Readable bytes or an explicit scope exclusion would unblock extraction; successful
full-population extraction is a separate discharge property. **Unestablished:** the
entire retained portfolio extraction, and whether these untracked bytes equal the
historical bytes at the Git base. No historical 6,417-file total is adopted as current.

## Remaining indexed rows

The remaining rows are still being measured. They will each receive the same four
questions and explicit unknowns before this workstream is considered complete.
