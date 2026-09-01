# Task N Debt Register Parser Repair Journal

## Session identity and scope

- Branch: `codex/debt-n-register-parser-repair`.
- Required base: `main` at `113b71aecc1f90fea91ef42b6378939725b176d2`.
- Parser/test delivery: `1050fb5cb5b3bf5e10907945a365378b858f6c51`.
- Starting state: attached, clean, and exactly at the required base.
- Branch attachment was read immediately before the parser/test commit.
- No branch-changing command or stash was used after the branch was created. No other lane branch or
  `.worktrees/` path was read.
- Changed mechanism paths: `tools/quality/validation/check_debt_ledger.py` and
  `tests/repo_quality/tools/test_debt_ledger_checker.py`.
- Record path: this append-only journal.
- `docs/plans/active/DEBT-REGISTER.md`, generated `docs/plans/active/LEDGER.md`, and every other
  path under `docs/plans/active/` were left byte-untouched for architect transcription.

## Pattern pass

- `P04`: status is load-bearing. The source cell, not a coincidental word elsewhere in the row,
  must determine the status.
- `P29` / `P38`: the property is “read the declared status cell” and “enumerate every list entry in
  the section.” Whole-row vocabulary and pipe-shaped header lines are proxies, not those properties.
- `P31`: the status repair is one header-derived intake rule for every register table, not a patch
  for the two currently mispublished ids.
- `P33`: the status test carries other status words in both id and subject, reorders the status
  column, quotes inline code containing an unmatched-for-the-regex backtick stream, and covers an
  absent status cell. The non-closure test covers both bullet and table forms and rejects a table
  header as data.
- `P35`: every count below comes from the complete 55-Markdown-file inventory returned by
  `_plan_inventory`; the executing party was this Task N lane.
- `P37`: the status predicate is `recomputed` from the table header plus the row's indexed cell.
  Missing or unrecognised cell content fails closed to `ambiguous`.
- `P41`: base and head were both executed from their exact parser sources. The register denominator
  remained 175, and no row moved out of `closed`.
- Before this repair both rows were `semantic_test_missing`: the checker existed, but no behavioral
  test proved that status authority and non-closure reach followed the document structure. The two
  named tests close that missing verification state.

## Red-first receipt

The tests were added before production code and invoked with:

```sh
uv run --frozen --extra test python -m pytest -q tests/repo_quality/tools/test_debt_ledger_checker.py::test_row_status_comes_from_the_status_cell_not_from_prose tests/repo_quality/tools/test_debt_ledger_checker.py::test_explicit_nonclosure_parser_reads_every_populated_section
```

Exit 1, with both failures occurring for the intended reasons:

```text
FAILED tests/repo_quality/tools/test_debt_ledger_checker.py::test_row_status_comes_from_the_status_cell_not_from_prose
E       AssertionError: assert [('closed-id', 'blocked')] == [('closed-id', 'open')]
FAILED tests/repo_quality/tools/test_debt_ledger_checker.py::test_explicit_nonclosure_parser_reads_every_populated_section
E       AssertionError: assert ['bullet-gap'] == ['bullet-gap', 'table-gap']
```

The later malformed-row adversarial addition also failed red before its guard was added:

```text
E   IndexError: list index out of range
tools/quality/validation/check_debt_ledger.py:152: IndexError
```

After the repair, the exact two-node command exits 0:

```text
..                                                                       [100%]
```

## Complete base/head register status delta

The base was measured before edits with the real base parser. It reported 175 rows. The following
command then reloaded the parser source and register bytes directly from the pinned base and compared
them with the committed head parser and the same authoritative register bytes:

```sh
PYTHONPATH=. python3 - <<'PY'
from pathlib import Path
from types import ModuleType
import subprocess
from tools.quality.validation import check_debt_ledger as head

base = "113b71aecc1f90fea91ef42b6378939725b176d2"
source = subprocess.run(
    ["git", "show", f"{base}:policy-engine/tools/quality/validation/check_debt_ledger.py"],
    cwd=Path.cwd().parent,
    check=True,
    capture_output=True,
    text=True,
).stdout
register = subprocess.run(
    ["git", "show", f"{base}:policy-engine/docs/plans/active/DEBT-REGISTER.md"],
    cwd=Path.cwd().parent,
    check=True,
    capture_output=True,
    text=True,
).stdout
base_parser = ModuleType("base_check_debt_ledger")
base_parser.__file__ = str(Path.cwd() / "tools/quality/validation/check_debt_ledger.py")
exec(compile(source, base_parser.__file__, "exec"), base_parser.__dict__)
base_rows = {row.debt_id: row.status for row in base_parser._parse_register(register)[0]}
head_text = (Path.cwd() / head.REGISTER_PATH).read_text(encoding="utf-8")
head_rows = {row.debt_id: row.status for row in head._parse_register(head_text)[0]}
print(f"BASE_ROWS={len(base_rows)}")
print(f"HEAD_ROWS={len(head_rows)}")
print(f"ADDED={sorted(head_rows.keys() - base_rows.keys())}")
print(f"REMOVED={sorted(base_rows.keys() - head_rows.keys())}")
changed = sorted(
    key for key in base_rows.keys() & head_rows.keys() if base_rows[key] != head_rows[key]
)
print(f"CHANGED={len(changed)}")
for key in changed:
    print(f"DELTA\t{key}\t{base_rows[key]}\t{head_rows[key]}")
print(
    "MOVED_OUT_OF_CLOSED="
    + repr([key for key in changed if base_rows[key] == "closed" and head_rows[key] != "closed"])
)
PY
```

Exact output:

```text
BASE_ROWS=175
HEAD_ROWS=175
ADDED=[]
REMOVED=[]
CHANGED=2
DELTA	ds9-human-decision-crash-test-fixture-blocked	blocked	open
DELTA	trust-posture-custody-appointment-requires-open-row	blocked	open
MOVED_OUT_OF_CLOSED=[]
```

This is the complete delta; there are no omitted changed ids.

| Row id | Base | Head | Defect path and exact evidence |
| --- | --- | --- | --- |
| `ds9-human-decision-crash-test-fixture-blocked` | `blocked` | `open` | Path 1: a paired backticked `blocked` token in subject prose precedes the paired status-cell token. Legacy paired status sequence: `['blocked', 'open', 'blocked']`; legacy whole-row result `blocked`; authoritative cell `` `open` ``. The id also contains the bare word `blocked`, but fallback was not needed for this row. |
| `trust-posture-custody-appointment-requires-open-row` | `blocked` | `open` | Path 1: paired backticked `blocked` prose precedes the paired status-cell token. Legacy paired status sequence: `['blocked', 'blocked', 'open', 'blocked']`; legacy whole-row result `blocked`; authoritative cell `` `open` ``. |

No currently changed row uses path 2. The register's 2026-09-01 wording workaround had already
removed the path-2 trigger from `explicit-nonclosure-check-blind-to-table-shaped-lists`. The named
regression test restores that adversary without editing the register: its subject quotes
`` ``^-\s+`([^`]+)` `` ``, which destroys whole-row backtick pairing, while status still comes from
the header-indexed cell. A missing or unrecognised cell becomes `ambiguous`; prose is never scanned
as a rescue.

Stop-rule disposition:

- No row moved out of `closed`; stop rule 1 did not trigger.
- No register table shape changed; stop rule 2 did not trigger.
- Every needed status index was derived from the literal `status` table header, including section F
  after its introductory prose; no section/index map was added, so stop rule 3 did not trigger.
- `PUBLISHED_DENOMINATORS["register"]` remains 175 and was not moved.

## Explicit non-closure denominator: before and after

The complete comparison command was:

```sh
PYTHONPATH=. python3 - <<'PY'
from collections import Counter
from pathlib import Path
from types import ModuleType
import subprocess
from tools.quality.validation import check_debt_ledger as head

root = Path.cwd()
base = "113b71aecc1f90fea91ef42b6378939725b176d2"
source = subprocess.run(
    ["git", "show", f"{base}:policy-engine/tools/quality/validation/check_debt_ledger.py"],
    cwd=root.parent,
    check=True,
    capture_output=True,
    text=True,
).stdout
base_parser = ModuleType("base_check_debt_ledger")
base_parser.__file__ = str(root / "tools/quality/validation/check_debt_ledger.py")
exec(compile(source, base_parser.__file__, "exec"), base_parser.__dict__)
_, _, paths = head._plan_inventory(root)
base_rows = base_parser._explicit_nonclosures(root, paths)
head_rows = head._explicit_nonclosures(root, paths)
base_counts = Counter(path for _, path, _ in base_rows)
head_counts = Counter(path for _, path, _ in head_rows)
section_paths = [
    path.relative_to(root).as_posix()
    for path in paths
    if "## Explicit non-closure" in path.read_text(encoding="utf-8")
]
print(f"PLAN_MARKDOWN_PATHS={len(paths)}")
print(f"EXPLICIT_SECTION_PATHS={len(section_paths)}")
for path in sorted(section_paths):
    print(
        f"FILE\t{path}\tbase={base_counts[path]}\thead={head_counts[path]}"
        f"\tdelta={head_counts[path] - base_counts[path]}"
    )
print(f"BASE_TOTAL={len(base_rows)}")
print(f"HEAD_TOTAL={len(head_rows)}")
print(f"TOTAL_DELTA={len(head_rows) - len(base_rows)}")
PY
```

Exact output:

```text
PLAN_MARKDOWN_PATHS=55
EXPLICIT_SECTION_PATHS=5
FILE	docs/plans/active/atlas-slices/DS10-capability-discovery.md	base=0	head=12	delta=12
FILE	docs/plans/active/atlas-slices/DS11-trust-docs-posture.md	base=7	head=7	delta=0
FILE	docs/plans/active/atlas-slices/DS17-confidence-ledger-risk-spend.md	base=0	head=10	delta=10
FILE	docs/plans/active/atlas-slices/DS8-case-evidence-workspace.md	base=0	head=0	delta=0
FILE	docs/plans/active/atlas-slices/DS9-human-decision-integrity.md	base=0	head=0	delta=0
BASE_TOTAL=7
HEAD_TOTAL=29
TOTAL_DELTA=22
```

### Required correction to the supplied denominator

The task brief's `30 = 12 + 7 + 11` is refuted at the pinned base. DS17 has ten table data rows,
at lines 2222 through 2231 inclusive. Its line 2220 is the table header and line 2221 the separator.
Calling the header an eleventh debt would make the parser report 30, but it would create a false
`capability` debt and reproduce P38/P35 inside the repair. The property-correct parsed denominator is
therefore **29 = 12 DS10 table rows + 7 DS11 bullet rows + 10 DS17 table rows**.

DS8's section is prose and DS9's is a numbered narrative list without entry ids; neither is one of
the requested bullet/table shapes. They remain zero. No source document was changed to force the
arithmetic.

### Newly visible check results

The head parser exposes 22 table entries that the base parser could not see. The unbound checker now
reports `explicit_nonclosure_missing` for this exact set:

DS10 (12):

1. `admitted-adapter-capability-discovery-bridge`
2. `connector-acquisition-content`
3. `debt-checker-frontend-denominator-label`
4. `default-causal-method-capabilityindex-bridge`
5. `ds6-c13-print-receipt-reissue`
6. `g2-g3-gl-rejected-incompleteness-richness`
7. `generic-post-g0-registry-data-only-free-growth`
8. `global-case-index`
9. `l4-world-agent-lookup`
10. `lex-pipeline-mutation`
11. `owner-signed-typed-capability-purpose-authority-binding`
12. `public-decision-rendering`

DS17 (10):

1. `c05-bayesian-without-coverage-semantic-visual-witness`
2. `c05-code-over-spend-code-end-to-end-semantic-visual-witness`
3. `closed-shadow-root-paint-observation`
4. `debt-register-other-slice-evidence-deep-import-baseline`
5. `eligible-positive-promotion-certificate-producer`
6. `institutional-authority-appointments`
7. `int-r1-code-bounded-complete-code-issuance`
8. `live-deployment-wide-ledger-scope-index`
9. `persisted-semantic-receipt-and-n12-projection-artifacts`
10. `public-claim-and-first-governed-promotion`

The checker also reports the two exact ledger status mismatches from the status delta and
`ledger_render_drift`. None was suppressed, and `LEDGER.md` was not regenerated in this lane.

## Required verification receipts

### Unbound debt-ledger checker

Exact command:

```sh
PYTHONPATH=. python3 tools/quality/validation/check_debt_ledger.py --check
```

At the base this exited 0 with `register_ids=175`,
`closure_signal_identity_unresolvable=0`, and no blocking findings. At head it exits 1. Its exact
head metrics are:

```text
register_ids=175
gy_ids=38
atlas_debt_rows=22
frontend_disposition_entries=261
frontend_ds8_assignment_rows=217
gy_history_blocks=6
gy_absent_from_register=15
gy_absent_from_register_closed=15
ds5_nonclosure_rows=27
ds5_planless_routes=4
irregular_section_e_branch_rows=1
closure_signal_pytest_selections=41
closure_signal_unsupported_runners=1
closure_signal_identities_without_commands=4
closure_signal_identity_unresolvable=0
closure_signal_input_unresolvable=0
closure_signal_selects_nothing=0
closure_signal_collection_failed=0
closure_signal_collection_host_unknown=41
closure_signal_ast_collection_disagreements=0
closure_signal_count_exit_disagreements=0
```

The blocking findings are exactly the 22 `explicit_nonclosure_missing` identities listed above,
the following two status findings, and render drift:

```text
ledger_render_drift: docs/plans/active/LEDGER.md
ledger_status_mismatch: ds9-human-decision-crash-test-fixture-blocked: source=open, ledger=blocked
ledger_status_mismatch: trust-posture-custody-appointment-requires-open-row: source=open, ledger=blocked
```

The remaining unbound output is informational: 41
`closure_signal_collection_host_unknown` findings because the raw interpreter is not bound to
`uv.lock`, one intentionally unsupported Vitest runner, and the existing register/source standing
relations. It does not alter the blocking set above.

### Docs lifecycle

Exact command:

```sh
PYTHONPATH=. python3 tools/quality/validation/check_docs_lifecycle.py
```

Exit 1 with exactly six findings. The stale path's slash is source-encoded as `&#47;` below so this
quotation does not itself become a seventh direct-reference finding; rendered Markdown is verbatim:

```text
Docs lifecycle gate FAILED:
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `status` front matter.
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `owner` front matter.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-adoption-ledger.json: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-archive-map.json: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/reference/frontend/atlas-v15-adjudication.md: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
```

No seventh docs-lifecycle finding was introduced.

### Targeted test file

Exact command:

```sh
uv run --frozen --extra test python -m pytest -q tests/repo_quality/tools/test_debt_ledger_checker.py
```

Exit 1 after the bound collection phase. The two new named tests pass. The seven reported failures
are, verbatim:

```text
FAILED tests/repo_quality/tools/test_debt_ledger_checker.py::test_real_census_replays_published_invariants
FAILED tests/repo_quality/tools/test_debt_ledger_checker.py::test_ds10_debt_projection_exposes_every_unresolvable_signal
FAILED tests/repo_quality/tools/test_debt_ledger_checker.py::test_real_ledger_exposes_every_gy_block_receipt_and_typed_state
FAILED tests/repo_quality/tools/test_debt_ledger_checker.py::test_capability_states_require_evidence_scoped_to_the_debt_subject
FAILED tests/repo_quality/tools/test_debt_ledger_checker.py::test_open_work_records_property_posture_and_branch_relevance
FAILED tests/repo_quality/tools/test_debt_ledger_checker.py::test_ds9_claims_and_splits_only_approved_debt_scope
FAILED tests/repo_quality/tools/test_debt_ledger_checker.py::test_real_ledger_is_the_deterministic_rendering
```

Material assertions:

```text
test_real_census_replays_published_invariants: assert 175 == 120
test_ds9_claims_and_splits_only_approved_debt_scope: assert 'G' == 'B'
test_real_ledger_is_the_deterministic_rendering: committed LEDGER.md != repaired parser rendering
```

The 120-row assertion is directly refuted by the exact base parser's 175-row census. The five other
real-state assertions before the deterministic-rendering check bind register/master-plan states that
are already present at the base and whose statuses are outside the exact two-row delta. The final
deterministic-rendering failure is an intended consequence of this task: the lane is forbidden to
regenerate `LEDGER.md`, while the repaired parser correctly expects two `open` rows. The exact
whole-file command was not replayed in a second base checkout, so this journal does not upgrade the
suite-level provenance classification beyond those direct base receipts.

### Ruff

Exact command over every changed Python file:

```sh
.venv/bin/python -m ruff check tools/quality/validation/check_debt_ledger.py tests/repo_quality/tools/test_debt_ledger_checker.py
```

Exit 0, verbatim:

```text
All checks passed!
```

### Final bound debt-ledger checker

The tree was clean and attached to `codex/debt-n-register-parser-repair` at
`1050fb5cb5b3bf5e10907945a365378b858f6c51` before this sole explicit bound checker run.

Exact command:

```sh
PYTHONPATH=. uv run --frozen --extra test python tools/quality/validation/check_debt_ledger.py --check
```

Exit 1. Exact metrics:

```text
register_ids=175
gy_ids=38
atlas_debt_rows=22
frontend_disposition_entries=261
frontend_ds8_assignment_rows=217
gy_history_blocks=6
gy_absent_from_register=15
gy_absent_from_register_closed=15
ds5_nonclosure_rows=27
ds5_planless_routes=4
irregular_section_e_branch_rows=1
closure_signal_pytest_selections=41
closure_signal_unsupported_runners=1
closure_signal_identities_without_commands=4
closure_signal_identity_unresolvable=10
closure_signal_input_unresolvable=0
closure_signal_selects_nothing=0
closure_signal_collection_failed=0
closure_signal_collection_host_unknown=0
closure_signal_ast_collection_disagreements=0
closure_signal_count_exit_disagreements=10
```

The exact `closure_signal_identity_unresolvable` identity set is:

1. `DS11-EXTERNAL-A11Y-COUNTERSIGN`
2. `DS11-FULL-TRUST-CENTER-AND-DOCS-IA`
3. `DS11-GROUNDED-PERFORMANCE`
4. `DS11-PUBLIC-SIGNATURE-POPULATION`
5. `DS11-SCOPE-ADJUDICATION-RECORD`
6. `ds10-connector-acquisition-content`
7. `ds10-global-case-index-producer-allocation`
8. `ds10-public-decision-rendering`
9. `epoch-dependency-denominator-defined-twice-incompatibly`
10. `global-case-index-producer-missing`

The `closure_signal_count_exit_disagreement` identity set is exactly the same ten. The bound run
also reports the 22 newly visible table non-closures, the two ledger status mismatches, and render
drift. `closure_signal_input_unresolvable`, `closure_signal_selects_nothing`,
`closure_signal_collection_failed`, `closure_signal_collection_host_unknown`, and
`closure_signal_ast_collection_disagreements` are all zero. Nothing was loosened to make this red
disappear.

## Exact append-only prose for architect transcription

### `register-status-parsed-from-prose-not-from-the-status-cell`

> 2026-09-01 Task N — **implementation landed; architect transcription and generated-ledger refresh
> remain.** At `1050fb5cb5b3bf5e10907945a365378b858f6c51`, `_parse_register` derives the
> status-column index from each table's literal `status` header and reads only that cell for sections
> A/B/C/D/F; section E stays forced `folded`, section G stays forced `closed`, and a missing or
> unrecognised status cell becomes `ambiguous`. The exact base/head comparison at
> `113b71aecc1f90fea91ef42b6378939725b176d2 -> 1050fb5cb5b3bf5e10907945a365378b858f6c51`
> holds the register denominator at 175 and changes exactly two rows, both `blocked -> open`:
> `ds9-human-decision-crash-test-fixture-blocked` and
> `trust-posture-custody-appointment-requires-open-row`. Neither moved out of `closed`; both current
> errors were path 1, an earlier paired backticked `blocked` token in id/subject material. The named
> regression also preserves path 2 with a subject quoting inline code containing a backtick, a
> reordered status column, and a missing-cell negative control. The two-node test exits 0 and Ruff is
> clean. `LEDGER.md` was deliberately not regenerated in this lane; its two status mismatches and
> render drift are the architect's transcription/regeneration receipt, never a reason to reword the
> register around the parser.

### `explicit-nonclosure-check-blind-to-table-shaped-lists`

> 2026-09-01 Task N — **table reach is repaired and the inherited denominator claim is corrected.**
> At `1050fb5cb5b3bf5e10907945a365378b858f6c51`, `_explicit_nonclosures` reads bullet entries and
> Markdown table data rows inside every `## Explicit non-closure` section, skips table headers and
> separators, preserves inline ids, and deterministically slugs plain first-cell identities. A
> complete walk of all 55 plan Markdown files finds five matching section headings and three
> bullet/table populations. The real parser delta is 7 -> 29: DS10 0 -> 12, DS11 7 -> 7, DS17
> 0 -> 10; DS8 prose and DS9 numbered narrative remain outside the requested shapes. The earlier
> `30 = 12 + 7 + 11` statement is refuted at the pinned base: DS17 has ten data rows at lines
> 2222-2231; its supposed eleventh row is the `capability` table header, and counting it would
> manufacture a false debt. The named behavioral test therefore pins the property-correct denominator
> 29, not the proxy 30. The repaired check exposes 22 `explicit_nonclosure_missing` findings—twelve
> from DS10 and ten from DS17—and none was suppressed or smoothed by editing a plan. Those findings
> and the corrected denominator require architect adjudication; the source tables remain untouched.
