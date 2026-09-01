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

## Continuation correction — entry count is not debt identity

This is an append-only correction to the preceding Task N entry. The earlier statement that table
labels were "deterministically slugged" describes the defect, not the repair. The resulting 22
`explicit_nonclosure_missing` findings were invented identifiers and are **not** an architect
adjudication set. The accepted denominator is 29, not 30, and those 29 entries split into 7 entries
that literally carry a debt id and 22 that do not.

The continuation landed in commit
`c5ad29cc7b4eb6536444ee01518b6c6beea32c09` on
`codex/debt-n-register-parser-repair`. No plan document or register row was edited. The only file
under `docs/plans/active` changed by the continuation is generated `LEDGER.md`, regenerated through
the checker's own `--write` path so the already-accepted two-row status correction is published.

### P38 correction

- Property: an entry has a debt identity only when that identity appears verbatim in its identity
  position — `- \`id\`` for a bullet, or an exact inline-code value in the table's first/entry cell.
- Old proxy: slugify the table's human-readable first cell.
- Divergent case: DS10's `generic post-G0 registry data-only free growth` label was converted to
  `generic-post-g0-registry-data-only-free-growth`, although the real register id is
  `ds10-adapter-registry-data-only-free-growth`; DS17's first row additionally leaked `<code>`
  markup into its slug.
- Correct mechanism: count every data row, carry `debt_id=None` for prose labels, apply
  `explicit_nonclosure_missing` only to literal identities, and emit one
  `explicit_nonclosure_unidentified` informational finding per unidentified source line.

`explicit_nonclosure_unidentified` is intentionally non-blocking. A source line with no id is a
document defect, not evidence that a particular ledger debt is missing. Making that absence red
would recreate a gate with no actionable identity.

## Red/green receipt

The named test was extended before the implementation. Exact red command:

```sh
uv run --frozen --extra test python -m pytest -q tests/repo_quality/tools/test_debt_ledger_checker.py::test_explicit_nonclosure_parser_reads_every_populated_section
```

Exit 1 for the intended reason:

```text
At index 1 diff: ('table-gap', 'table.md', 7) != (None, 'table.md', 7)
```

After the literal-identity repair, the same command exits 0:

```text
.                                                                        [100%]
```

The fixture proves all four required behaviors in one test: bullet identity, exact table identity,
prose table entry with no identity, and the blocking/informational split. Its real-inventory branch
pins 29 entries, 7 identified, 22 unidentified and verifies that every emitted id appears verbatim
inside backticks on its own source line.

## Corrected non-closure census

Exact command:

```sh
PYTHONPATH=. python3 - <<'PY'
from collections import Counter
from tools.quality.validation import check_debt_ledger as checker

_, _, paths = checker._plan_inventory(checker.REPO_ROOT)
entries = checker._explicit_nonclosures(checker.REPO_ROOT, paths)
identified = [entry for entry in entries if entry.debt_id is not None]
unidentified = [entry for entry in entries if entry.debt_id is None]
synthetic = []
for entry in identified:
    source = (checker.REPO_ROOT / entry.path).read_text(encoding="utf-8").splitlines()[entry.line - 1]
    if f"`{entry.debt_id}`" not in source:
        synthetic.append(entry)
print(f"entries={len(entries)} identified={len(identified)} unidentified={len(unidentified)}")
print(f"per_file={dict(sorted(Counter(entry.path for entry in entries).items()))}")
print(f"synthetic={synthetic}")
PY
```

Verbatim summary:

```text
entries=29 identified=7 unidentified=22
per_file={'docs/plans/active/atlas-slices/DS10-capability-discovery.md': 12, 'docs/plans/active/atlas-slices/DS11-trust-docs-posture.md': 7, 'docs/plans/active/atlas-slices/DS17-confidence-ledger-risk-spend.md': 10}
synthetic=[]
```

Complete source-line inventory:

| file | shape | entries | identified | unidentified |
| --- | --- | ---: | --- | --- |
| `docs/plans/active/atlas-slices/DS10-capability-discovery.md` | table | 12 | none | 1150, 1151, 1152, 1153, 1154, 1155, 1156, 1157, 1158, 1159, 1160, 1161 |
| `docs/plans/active/atlas-slices/DS11-trust-docs-posture.md` | bullets | 7 | 1293 `DS11-CLAIM-LIFECYCLE-ORCHESTRATION`; 1297 `DS11-PUBLIC-SIGNATURE-POPULATION`; 1300 `DS11-SCOPE-ADJUDICATION-RECORD`; 1304 `DS11-EXTERNAL-A11Y-COUNTERSIGN`; 1307 `DS11-GROUNDED-PERFORMANCE`; 1310 `DS11-INHERITED-C13-PRINT-RECEIPT`; 1314 `DS11-FULL-TRUST-CENTER-AND-DOCS-IA` | none |
| `docs/plans/active/atlas-slices/DS17-confidence-ledger-risk-spend.md` | table | 10 | none | 2222, 2223, 2224, 2225, 2226, 2227, 2228, 2229, 2230, 2231 |
| **total** | bullet + table | **29** | **7** | **22** |

There are zero synthetic identifiers anywhere in `_explicit_nonclosures` output. In particular,
the seven historical DS10 register ids mentioned later in closure-signal prose are not mined from
other cells: an owner, command, status token or historical cross-reference is not the entry's
identity.

## Continuation register-status delta

The accepted status parser was not changed. The continuation comparison executed the parser from
`d37cf70154a73854ee066cfc68647b674d6c22d1` directly from its Git blob and the parser at the
continuation head over the same current register bytes. The operative comparison was:

```sh
PYTHONPATH=. python3 - <<'PY'
from collections import Counter
from hashlib import sha256
from pathlib import Path
import subprocess
from tools.quality.validation import check_debt_ledger as head

commit = "d37cf70154a73854ee066cfc68647b674d6c22d1"
source = subprocess.run(
    ("git", "show", f"{commit}:policy-engine/tools/quality/validation/check_debt_ledger.py"),
    check=True,
    capture_output=True,
    text=True,
).stdout
namespace = {
    "__file__": str(Path("tools/quality/validation/check_debt_ledger.py").resolve()),
    "__name__": "check_debt_ledger_at_continuation_base",
}
exec(compile(source, namespace["__file__"], "exec"), namespace)
text = Path("docs/plans/active/DEBT-REGISTER.md").read_text(encoding="utf-8")
base_rows, _ = namespace["_parse_register"](text)
head_rows, _ = head._parse_register(text)
base = {row.debt_id: row.status for row in base_rows}
current = {row.debt_id: row.status for row in head_rows}
changed = [
    (debt_id, base.get(debt_id), current.get(debt_id))
    for debt_id in sorted(base | current)
    if base.get(debt_id) != current.get(debt_id)
]
for label, mapping in (("base", base), ("head", current)):
    payload = "\n".join(f"{debt_id}\t{mapping[debt_id]}" for debt_id in sorted(mapping))
    print(f"{label}_rows={len(mapping)}")
    print(f"{label}_statuses={dict(sorted(Counter(mapping.values()).items()))}")
    print(f"{label}_mapping_sha256={sha256(payload.encode()).hexdigest()}")
print(f"added={sorted(current.keys() - base.keys())}")
print(f"removed={sorted(base.keys() - current.keys())}")
print(f"changed={changed}")
PY
```

Verbatim result:

```text
base_rows=175
base_statuses={'ambiguous': 1, 'blocked': 39, 'closed': 100, 'folded': 2, 'foreign': 6, 'open': 27}
base_mapping_sha256=3c238975c355ec083662f76c76660fb00eda473da35ce950101d5b0f75b5b633
head_rows=175
head_statuses={'ambiguous': 1, 'blocked': 39, 'closed': 100, 'folded': 2, 'foreign': 6, 'open': 27}
head_mapping_sha256=3c238975c355ec083662f76c76660fb00eda473da35ce950101d5b0f75b5b633
added=[]
removed=[]
changed=[]
```

The continuation status delta is exactly empty. No stop rule fired.

## Optional third item — stale checker tests repaired with causes

The optional item was taken because every moved value became causally accountable. The six stated
metric pins now read:

| metric | pinned at | stale -> current | cause |
| --- | --- | ---: | --- |
| `register_ids` | `313132b6b0` | 120 -> 175 | Nineteen first-parent register commits added a net 55 literal ids; complete list below. |
| `ds5_planless_routes` | `76be63c1ff` | 6 -> 4 | After a transient 6 -> 11 -> 6 DS9 inventory round-trip, `6b8ab34559` added the DS18 plan (6 -> 5) and `2c8e1c03ce` added the DS15 plan (5 -> 4). The 27 DS5 rows did not change. |
| `closure_signal_pytest_selections` | `4ff11db527` | 32 -> 41 | Nine net literal pytest selections were added across the exact register commits listed below. |
| `closure_signal_identities_without_commands` | `9833279596` | 1 -> 4 | `db051c70d0`, `83f69c3c00` and `be17df6cee` each added one bare pytest identity outside a parsed command. |
| `closure_signal_identity_unresolvable` | `4ff11db527`, bound interpreter | 18 -> 10 | Ten base identities became real, two new unresolved identities were registered, and transient additions/resolutions reconcile exactly; transition and final sets are below. |
| `closure_signal_count_exit_disagreements` | `4ff11db527`, bound interpreter | 18 -> 10 | Same ten identities as `identity_unresolvable`: each selects zero while pytest exits 4 (`unresolvable`), so the count and exit readings disagree for the same set. |

The collection-dependent pins are asserted only after
`_collection_environment_issue(REPO_ROOT) is None`. Under the unbound interpreter both degrade to
0 and `closure_signal_collection_host_unknown=41`; the test deliberately fails its bound-precondition
instead of silently pinning those degraded zeros.

### Register growth from the 120 pin

The first-parent census used `git rev-list --first-parent --reverse
313132b6b0..d37cf7015`, `git show <commit>:policy-engine/docs/plans/active/DEBT-REGISTER.md`,
and the current row parser. Exact count-changing commits:

```text
716261ab29  120->129 (+9)  docs: record the DS18 closure and its three findings
58a040c879  129->130 (+1)  docs: record the DS18 reopening and close the landing-red row
df90e10fb4  130->138 (+8)  docs: record the DS15 closure and its eight declared non-closures
73d930f828  138->147 (+9)  docs: route wave 5 into the three planning documents
7408df9f6b  147->151 (+4)  docs: record the promotion-gate obligation experiment
7080287569  151->153 (+2)  docs(rulings): appointment binds the act, and DS20 is two rows
47ffc328c9  153->154 (+1)  docs(register): transcribe Task E round 2 — six rows blocked, one new owner gap
602923671f  154->156 (+2)  docs(register): both rulings dissolved on reading; two orchestration gaps get rows
7e7ca67324  156->157 (+1)  docs(register): the EFFECT question is answered, and my framing was the error
b2b3897d99  157->160 (+3)  docs(register): task F closes its whole set — the declared cycle is gone
db051c70d0  160->162 (+2)  docs(register): task D — the dashboard freeze, three closures, one declined block
3681f22fa2  162->163 (+1)  docs(register): tasks A and J close — the promotion gate has no absent capability left
5380906c5e  163->164 (+1)  docs(register): task K — two closures, and my stop rule pointed it at the wrong instrument
e31e72ccbb  164->165 (+1)  docs(register): correct my own overstatement — one cell is not clean
2398881f5e  165->166 (+1)  docs(register): task L closes all five census rows, none by renaming an absence
be17df6cee  166->168 (+2)  docs(debt): transcribe task G — five closures, six censused blockers, two new rows
ef0e24ad7a  168->170 (+2)  docs(debt): register the DS11 trust-posture guardrail, red and unwatched
03d077259c  170->171 (+1)  docs(debt): transcribe task C — eight closures, four blockers, one blind check
e91e5c30a8  171->175 (+4)  docs(debt): transcribe task B, and record that main is red
```

These deltas sum to +55 exactly.

### Static closure-signal movement

Exact first-parent changes from the 32/1 pins:

```text
7080287569  pytest 32->33 (+1); identity-only 1->1 (+0)
0b78163505  pytest 33->34 (+1); identity-only 1->1 (+0)
c4ea773826  pytest 34->33 (-1); identity-only 1->1 (+0)
db051c70d0  pytest 33->34 (+1); identity-only 1->2 (+1)
83f69c3c00  pytest 34->35 (+1); identity-only 2->3 (+1)
be17df6cee  pytest 35->36 (+1); identity-only 3->4 (+1)
ef0e24ad7a  pytest 36->38 (+2); identity-only 4->4 (+0)
03d077259c  pytest 38->39 (+1); identity-only 4->4 (+0)
e91e5c30a8  pytest 39->41 (+2); identity-only 4->4 (+0)
```

### Bound unresolved-identity movement

The first-parent set transition from the 18 pin is:

```text
4ff11db527  18
7080287569  19  + runtime-authorization-denominator-reconciliation
a638ad250a  18  - runtime-authorization-denominator-reconciliation
f6b2e8c68f  15  - DS11-CLAIM-LIFECYCLE-ORCHESTRATION
                  - DS11-GENERAL-COPY-SEMANTICS
                  - DS11-PUBLISHED-SIGNATURE-WATCHER
be17df6cee  16  + global-case-index-producer-missing
ee32c2b27f  10  - ds10-adapter-admission-capability-discovery-bridge
                  - ds10-adapter-registry-data-only-free-growth
                  - ds10-causal-method-index-provider-bridge
                  - ds10-layer3-owner-ledger-rejection-richness
                  - ds10-owner-signed-capability-purpose-binding
                  - ds10-world-agent-capability-discovery-boundary
03d077259c  11  + explicit-nonclosure-check-blind-to-table-shaped-lists
bc5b59b182  10  - decision-validity-fixed-temp-concurrency
e91e5c30a8  12  + epoch-dependency-denominator-defined-twice-incompatibly
                  + register-status-parsed-from-prose-not-from-the-status-cell
1050fb5cb5  10  - explicit-nonclosure-check-blind-to-table-shaped-lists
                  - register-status-parsed-from-prose-not-from-the-status-cell
```

Direct base/head comparison therefore has ten resolved identities and two additions, net 18 -> 10.
The ten resolved identities are the three DS11 rows, six DS10 rows and
`decision-validity-fixed-temp-concurrency`; the two additions are
`global-case-index-producer-missing` and
`epoch-dependency-denominator-defined-twice-incompatibly`.

The full-file replay also exposed real-state assertions hidden behind the first stale assertion.
They were updated only after their source transitions were identified:

| stale expectation | current truth | cause |
| --- | --- | --- |
| nine unresolved DS10 signals | three unresolved: global case index, connector/acquisition, public decision | six tests became real in `ee32c2b27f`. |
| `GY-GAP8` rendered open | closed and absent from the open ledger | `83f69c3c00`. |
| `three-unavailable-governed-producers` rendered open | closed and absent from the open ledger | Task C transcription `03d077259c`. |
| DS15 and DS17 in open-work Table A | both absent | slice merges `2c8e1c03ce` and `8c58085ca`. |
| DS8 local reviewer note in B/open | G/closed | Task G transcription `be17df6cee`. |
| DS8 signed public decision open | B/blocked | Task G transcription `be17df6cee`. |
| `GY-DEF23` open | B/blocked | Task B transcription `e91e5c30a8`. |
| fixed-temp concurrency C/ambiguous | A/blocked | Task B transcription `e91e5c30a8`; its selector became real in `bc5b59b182`. |
| informational-code set lacked the new class | includes `explicit_nonclosure_unidentified` | this continuation's explicit non-blocking visibility contract. |

No unexplained pin was moved. The eight other numeric pins in the real-state block remain unchanged.

## Continuation verification receipts

### Generated ledger refresh

Exact command:

```sh
PYTHONPATH=. python3 tools/quality/validation/check_debt_ledger.py --write
```

Exit 0. The generated diff moves only
`ds9-human-decision-crash-test-fixture-blocked` and
`trust-posture-custody-appointment-requires-open-row` from the blocked grouping to the open grouping
and changes the distribution from `blocked=41, open=25` to `blocked=39, open=27`. It changes no
register bytes and no row count.

### Unbound debt-ledger checker

Exact command:

```sh
PYTHONPATH=. python3 tools/quality/validation/check_debt_ledger.py --check
```

Exit 0. Exact metrics:

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
explicit_nonclosure_entries=29
explicit_nonclosure_identified=7
explicit_nonclosure_unidentified=22
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

There is no `Blocking findings:` section. The command emits 41 carried
`closure_signal_collection_host_unknown` informational findings, one carried unsupported-Vitest
finding, ten carried register/source-standing informational findings, and the exact 22
`explicit_nonclosure_unidentified` file/line findings enumerated above.

### Docs lifecycle

Exact command:

```sh
PYTHONPATH=. python3 tools/quality/validation/check_docs_lifecycle.py
```

Exit 1 with exactly the carried six findings. The stale slash is entity-encoded here so the journal
does not create a seventh direct-reference hit:

```text
Docs lifecycle gate FAILED:
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `status` front matter.
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `owner` front matter.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-adoption-ledger.json: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-archive-map.json: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/reference/frontend/atlas-v15-adjudication.md: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
```

### Targeted checker tests

Exact command:

```sh
uv run --frozen --extra test python -m pytest -q tests/repo_quality/tools/test_debt_ledger_checker.py
```

Final exit 0, 69 tests:

```text
.....................................................................    [100%]
```

Two earlier complete runs were intentionally retained as discovery evidence: the first exposed six
stale real-state tests after the numeric pins were corrected; the second narrowed the remainder to
two assertions that had been unreachable behind the first failures. Each moved assertion is mapped
to its source transition above; the final full-file run is green.

### Ruff

Exact command over every changed Python file:

```sh
.venv/bin/python -m ruff check tools/quality/validation/check_debt_ledger.py tests/repo_quality/tools/test_debt_ledger_checker.py
```

Exit 0, verbatim:

```text
All checks passed!
```

### Sole final bound checker

The tree was clean and attached to `codex/debt-n-register-parser-repair` at
`c5ad29cc7b4eb6536444ee01518b6c6beea32c09` before this sole continuation bound-checker run.

Exact command:

```sh
uv run --frozen --extra test python tools/quality/validation/check_debt_ledger.py --check
```

Exit 1 with exact bound metrics:

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
explicit_nonclosure_entries=29
explicit_nonclosure_identified=7
explicit_nonclosure_unidentified=22
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

Exact `closure_signal_identity_unresolvable` identity set:

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

`closure_signal_count_exit_disagreement` has the same ten identities. The blocking exit is carried
and was not weakened; none of its identities comes from an unidentified non-closure entry.

## Corrected exact prose for architect transcription

### `explicit-nonclosure-check-blind-to-table-shaped-lists`

> 2026-09-01 Task N continuation — **closed by literal identity, not by a slug.** Commit
> `c5ad29cc7b4eb6536444ee01518b6c6beea32c09` preserves the complete document measurement while
> separating entry existence from debt identity. `_explicit_nonclosures` parses both bullet and
> table data rows in every populated `## Explicit non-closure` section, but emits a debt id only
> when that id appears verbatim as a bullet's leading inline-code token or as the exact inline-code
> value of a table's first/entry cell. It never derives, slugifies, normalises or mines an id from
> prose, owner, status, command or historical cross-reference cells. The complete 55-plan Markdown
> inventory measures **29 entries = 7 identified + 22 unidentified**: DS10 **12 = 0 + 12** at
> lines 1150-1161, DS11 **7 = 7 + 0** at lines 1293/1297/1300/1304/1307/1310/1314, and DS17
> **10 = 0 + 10** at lines 2222-2231. The parser-wide literal-source check reports
> `synthetic=[]`. `explicit_nonclosure_missing` applies only to the seven identified entries; each
> unidentified entry emits one file/line `explicit_nonclosure_unidentified` informational finding,
> which cannot make the gate red because absence of an id does not establish a missing ledger debt.
> The unbound checker exits 0 with metrics `explicit_nonclosure_entries=29`,
> `explicit_nonclosure_identified=7`, `explicit_nonclosure_unidentified=22`; the named mixed-shape
> behavioral test passes, the 69-test checker file passes under the lock-bound interpreter, and Ruff
> is clean. No plan was edited to add an id. Closure requires the **29/7/22 split plus the literal-id
> invariant**, not a bare denominator. This supersedes the earlier 30-row/header census and the
> first Task N implementation's 22 invented blocking findings.

### New row: `debt-ledger-checker-real-state-pins-stale-unnoticed`

> 2026-09-01 Task N continuation — **register and close the checker's stale-real-state test debt.**
> `tests/repo_quality/tools/test_debt_ledger_checker.py` still pinned a 120-row register, six
> planless DS5 routes, 32 pytest selections, one identity without a command and 18 bound unresolved
> identities after the repository had moved to 175, 4, 41, 4 and 10 respectively. Five further
> real-state tests carried old open/blocked/closed and open-work projections, so the file could sit
> red while the checker itself continued to publish. Commit
> `c5ad29cc7b4eb6536444ee01518b6c6beea32c09` re-derived every moved value from Git history and real
> parser runs, preserved the eight still-exact numeric pins, declares the lock-bound interpreter
> precondition next to the two collection-dependent assertions, and updates only source transitions
> with named causes: DS18/DS15 plan merges, Task B/C/G transcriptions, DS15/DS17 slice merges and the
> exact closure-signal set changes. No unexplained pin moved. The exact targeted file now exits 0 at
> **69/69**, the unbound checker exits 0, and the sole final bound checker retains its honest ten-id
> blocking set. Closure signal: `uv run --frozen --extra test python -m pytest -q
> tests/repo_quality/tools/test_debt_ledger_checker.py` exits 0 under the repository's lock-bound
> interpreter, and any future real-state pin change must name its source transition rather than be
> bulk-repinned.
