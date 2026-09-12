---
title: Register consumers must preserve tokens and reuse parsed status
status: stage1-decision-awaiting-committed-readback
owner: team-devx / team-architecture
authoritative_for:
  - bounded source-consumer research and proposed repair scope
may_not_use_for:
  - debt standing or closure evidence
  - ownership or custody appointment authority
  - permission to edit register or ledger bytes
  - evidence of Stage2 implementation
---

# Row 2 — consumer format decision

Decision: **option 2, a token-based consumer requirement**. The retained literal
pipes are inputs the consumers must handle; sanitizing author text is not an
available repair. Root serializes implementation and commits these Stage1 docs
before source work. This document does not reopen `_parse_register`'s already
repaired status fallback.

All source coordinates below refer to product-root paths at
`42c09a7a46ac7ec42e39e4cc19a259a10b2c8811`. Neither restricted document was opened
or used as evidence. Root's reported generated-artifact check (260, zero blocking,
two shifts) is commissioning context, not a fresh finding of this research.

## Findings and complete denominator

**MP2-01 — independently reconciled source boundary.** `rows23/raw/census.py`
enumerates **12,875 tracked files under `policy-engine/`, all file types**, using
`git ls-files -z` and independently `git ls-tree --full-tree -rz --name-only
HEAD:policy-engine`; sets agree. The source suffix set has **7,521 files**:
6,176 `.py`, 5 `.pyi`, 517 `.ts`, 719 `.tsx`, 39 `.mjs`, 9 `.cjs`, 5 `.js`,
45 `.sh`, 6 `.sql`. Every Python/pyi AST was parsed: 76,866 function definitions,
13,139 classes, 677,162 calls. The TypeScript compiler parsed all 1,289 JS/TS
files: 12,954 definitions and 60,904 calls, zero parse errors. These are syntax
counts, not runtime invocation or semantic consumer counts.

`targeted_census.py` additionally scans all tracked `.rego`, `.cypher`, `.tf`,
`.html`, `.tmpl`, `.tpl` and extensionless paths: **7,575 source/template paths**
searched case-insensitively using `rg`, with complete output retained. Restricted
Markdown paths are enumerated by name only, never read. Python and JS/TS syntax
inventories retain every definition/call, not just a keyword sample. Shell/SQL
and supplemental files have literal search coverage, not an AST call graph.
Reflective construction, external installations, untracked code, and dynamic
runtime reads are outside this finite static result.

**MP2-02 — exact positional consumer census.** The following are the live
operational sites found by resolving the register reference and its admitted
`source_content` chain. Coordinates are navigation; function/property identity
is the binding. Shared `_cells` at `check_debt_ledger.py:117` splits every `|`.

| Consumer, product-relative path | Actual assumption | Caller / observable consequence |
| --- | --- | --- |
| `tools/quality/validation/check_debt_ledger.py:174`, `_parse_register` | `cells[0]` ID/header; header-derived status at 212 with repaired fallback; owner map A/B/C→2, D→1 at 246–249 | `_snapshot:585`; a subject pipe still shifts owner even when status recovers |
| Same file `:653`, `_owner_cells` | Reparses `row.raw`; `cells[1]` subject at 656 | `render_ledger:758`; subject-scoped capability label can disappear after a pipe |
| Same file `:855`, `_active_closure_signal` | Reparses `row.raw`; `cells[-1]` at 857 | `_parsed_selections:907` → `_closure_signal_findings:1206` → audit; a pipe inside the closure command truncates it |
| Same file `:1314`, `audit_repository` | Independent map A/B/C→3, D→2, F/G→1 at 1356; `_status_token(cells[status_index])` at 1362 | `main:1564`, workspace CI parity at `tools/devx/workspace/ci_parity.py:230`; recovered `open_unmerged` can miss its branch check |
| `tools/quality/validation/check_trust_claim_posture.py:371`, `derive_custody_appointments` | Split at 386; exactly 5 cells; ID 0, owner 2, status 3, command 4 | `compile_claim_posture_register:1183`; a content-preserving pipe in the subject makes the accepted set appear incomplete |
| `src/polisyos/scientist/evidence/claims/posture.py:1847`, `_validate_custody_appointments` | Split at 1863; exactly 5 cells; ID 0, owner 2, status 3, command 4 | `ClaimPostureRegisterV1.validate_register:1095`; rejects admitted `source_content` after digest verification |
| `apps/runtime-dashboard/src/features/trust/domain/posture.ts:1292`, `validateCustodyAppointments` | Split at 1318; exactly 5 cells; ID 0, owner 2, status 3, command 4 | validation at 2723; returns false on the same admitted-row format |

`_snapshot:594` also scans the carried-closed tail by marker and ID regex; it is
a semantic consumer, not a column-index consumer. `_parse_ledger_table:628` and
`audit_repository:1420` consume generated ledger cells, while `_parse_atlas_debts`,
`_parse_work`, `_slice_state`, `_ds5_metrics`, and `_explicit_nonclosures` use
the shared splitter for other tables. They are collateral consumers of any
change to `_cells`; they are not additional DEBT-REGISTER column parsers.

The complete source search also finds direct test readers in
`tests/repo_quality/tools/test_debt_ledger_checker.py`,
`tests/repo_quality/architecture/test_last_mile_cross_cutting_concerns.py`, and
`tests/repo_quality/tools/test_trust_claim_posture.py`; these were inspected as
code, not run against restricted files. Historical executable readers
`docs/superpowers/journals/gy-phase5-evidence/pr1/private_interpreter_owner_audit.py:87`
and `trust_posture_semantic_summary.py:42` retain/compare whole rows, not columns;
neither was executed. Search hits for `ds4-waist-debt-register.json` and
`compare_baseline.py`'s `import_debt_register.csv` concern different artifacts.
Path exclusion/allowlist hits in the journal probes, lifecycle checker and GY
checker are declarations, not reads of the restricted document. The retained
search output gives their complete coordinates.

**MP2-03 — executable divergence beyond the repaired parser.** In the synthetic
audit replay, the ordinary row produces `open_unmerged_branch_merged`. Adding
only subject text `` `left|right` `` leaves parsed status `open_unmerged`, records
the shift, corrupts owner to `right`, and emits **no branch finding**. The real
`audit_repository` ran with a synthetic snapshot, empty synthetic Atlas input,
and a controlled ancestor result; this proves gate selection, not a real branch
ancestry fact. Separate real-function probes show subject truncation after
holding the upstream owner constant, and loss of a pytest command prefix when
its quoted selector contains a pipe. No live row or generated ledger was read.

**MP2-04 — stale parser destructuring is separate caller work.** Full AST call
enumeration finds `_parse_register` calls at checker `:585`, test checker `:245`,
and cross-cutting test `:81`. The producer returns four values at `:261`; the
two test callers still unpack two. Fixing those callers is a required companion
when root exercises those tests, not grounds to revert the repaired producer.
No debt-status assertions from those tests are adopted here.

## Smallest root repair and composition

First remove the independent status re-read in `audit_repository`: use the
already parsed `row.status == "open_unmerged"` for the existing branch check.
Keep its ancestor semantics, finding codes, collection-only execution boundary,
and status-shift/unlocatable reporting. This closes MP2-03's demonstrated
secondary gate defect; **it alone does not close the format class** in MP2-02.

For the format class, route row slicing through token-aware syntax admission
before applying column roles. Header separators, escaped pipes, and pipes in
matched inline-code runs must be distinguished without rewriting original
bytes. Preserve complete subject/owner/closure spans and exact original bytes
for hashes. Ambiguous/malformed syntax must yield an explicit unresolved result;
do not invent an owner/status from incidental prose tokens. Reuse the current
consumer result types and existing status fallback. A search-found helper,
`tools/quality/validation/check_policy_design_case_drift.py:474`
`_split_markdown_row`, is another raw `split("|")`, not a ready tokenizer.

Owners must compose: DevX owns ledger parsing/reporting; Scientist claims owns
custody admission; frontend owns the browser validator; architecture owns the
permitted shared syntax placement. Do not make runtime import `tools`, or make
frontend depend on a Python implementation. The shared invariant is syntax and
cross-language behavioral vectors; each owner keeps its semantic authority.
Production callers of that proposed syntax work are exactly the operational
sites in MP2-02. This is an extension/consolidation of their intake paths, not
a new standalone diagnostic or a second register producer.

Authors meet the requirement at `tools/README.md` and `architecture/README.md`
entrypoints linked to scoped `tools/AGENTS.md` / `architecture/AGENTS.md`; source
and frontend owner guidance must link the same consumer rule. It belongs in
consumer author/review instructions and behavioral tests, **not a change to
the restricted register**. Root owns those Stage2 guidance edits.

Untouchable seams: register/ledger bytes and hashes; deliberate literal pipes;
standing/status authorities; custody accepted IDs, owner/command contracts and
digest binding; architecture/import boundaries; published denominator pins;
existing fallback behavior; unrelated lanes. A custody intake must continue
to resolve, bind and verify evidence—tokenization is syntax, not authority.
Shared effects require root to coordinate ledger, trust compiler, backend and
dashboard review; changing global `_cells` also reaches the non-register tables
identified above. Preserve their current semantics through owner tests.

## Acceptance, falsifiers and pattern pass

Falsifiers hold meaning fixed while varying formatting: subject code-span pipe,
escaped pipe, multi-backtick span, closure-command pipe, and a sibling consumer.
Then hold format fixed while changing status/owner/command/digest: real invalid
appointments and unresolvable statuses must still fail. Duplicate/contradictory
status candidates may not silently grant authority. The branch test must assert
the actual emitted finding through `audit_repository`, not the presence of a
new parser call. Removal of token admission while retaining names/docs must
break the semantic vectors. Root must also run the touched non-register table
tests if it changes shared `_cells`.

Pattern pass: **P31** covers all intake/reparse siblings; **P32** preserves
resolve/bind/verify; **P35** is MP2-01's complete typed denominator; **P37** labels
source membership `independently_reconciled`, syntax and replay outcomes
`recomputed`, real restricted-row outcomes `not_established`; **P38** distinguishes
intended status/field identity from the measured split index (MP2-03). The repair
is `semantic_test_missing` until repository owner tests exercise the full path;
this research is not implemented capability or debt closure.

## Replay receipts

All scratch paths below are under
`docs/superpowers/journals/measurement-plane/rows23/raw/` and gitignored.
From this worktree's product root:

```sh
uv run --no-sync python docs/superpowers/journals/measurement-plane/rows23/raw/census.py
uv run --no-sync python docs/superpowers/journals/measurement-plane/rows23/raw/targeted_census.py
node docs/superpowers/journals/measurement-plane/rows23/raw/typescript_census.cjs
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests:. uv run --no-sync python -m pytest -o addopts='' -p no:cacheprovider --confcutdir=docs/superpowers/journals/measurement-plane/rows23/raw --basetemp=docs/superpowers/journals/measurement-plane/rows23/raw/pytest-tmp-final docs/superpowers/journals/measurement-plane/rows23/raw/test_rows23_replay.py -q -s
```

Complete deciding outputs: `census-complete.out`, `targeted-census.out`,
`typescript-census.out`, `replay.out`; source census: `source-ast.jsonl`,
`typescript-ast.jsonl`, `rg-source-search.txt`, `target-ast.jsonl`. Receipt hashes
are retained in `receipt-hashes.json`. Earlier `census.out`, `replay-initial.out`
and `replay-second.out` record harness corrections, not excluded product-suite
failures. No commit, checkout, source repair or live checker invocation was made.

Verified research replay: **4 passed in 27.81 s**, exit 0. One pytest warning
records `cache_dir` with the cache provider deliberately disabled for scratch;
it is not a product failure. The earlier retained failures were scratch harness
assertion/serialization mistakes, corrected without changing repository owners.

## Root placement decision before execution

The Python syntax owner will be `src/polisyos/common/markdown.py`, a small
stdlib-only row tokenizer imported by the existing ledger, trust compiler and
Scientist custody validator. Common's existing serialization owner is JSON-only;
the complete Common Python AST walk plus case-insensitive Markdown/split discovery
found no table tokenizer there. Keep table syntax separate from JSON canonical
identity and from custody decisions. The browser counterpart lives beside its
existing posture consumer, with the same behavioral vectors; it does not load
Python or acquire a second status authority. These are internal helpers, not new
standalone tools: MP2-02's real producer/consumer paths invoke them.

Preserve the repaired register status fallback and its two informational recovery
signals: its raw physical-column observation remains diagnostic. Apply tokenized
cells to subject/owner/closure slicing, and make the branch checker consume the
parsed status. Do not globally change `_cells`, which serves unrelated tables.
Custody consumers tokenize before applying their fixed role grammar and keep
all digest, appointed-ID, status, owner and command checks. New helper imports
may expose a deep-import baseline delta; report it to architecture without sync,
with task status complete-pending-an-architect-decision when that is the only
remaining action. The preserved malformed/contradictory input negatives must
still withhold authority rather than infer roles from prose.


Generated-artifact feasibility constraint: after tokenizing subject/owner/closure
cells, the existing `check_debt_ledger --check` must still reconcile the retained
register and ledger at 260 with zero blocking and the same two informational
status recoveries. If corrected field interpretation changes generated ledger
bytes, the discrepancy must be reported as a real render-drift finding; this lane
may not update LEDGER.md or suppress that predicate. Such a result establishes an
owner regeneration dependency, not permission to weaken the checker or silently
retain a false owner. The final handback must separate syntax/rule delivery from
any closure that the protected generated artifact prevents.

## Stage 2 constraint outcome

Token-aware source consumers and their shared Python/TypeScript vectors are
implemented. The original status recovery is retained and still emits the two
known informational shifted-column rows. A synthetic real Git branch proves a
shifted `open_unmerged` row can no longer evade the merged-branch negative.

The forbidden generated-artifact constraint is decisive: the correct projection
changes exactly two owner cells, so unchanged canonical LEDGER fails
`ledger_render_drift`. The lane cannot deliver canonical green while preserving
both the correct reader and the user's no-LEDGER-edit requirement. No compatibility
wrong-owner rendering or drift exception is introduced. Owner regeneration via
the existing ledger writer is the remaining acceptance dependency. New Common
deep-import policy acceptance, if confirmed by the final guardrail, is separately
an architect decision; no guardrails sync is authorized. Complete evidence is
retained in the completion journal.

The complete canonical check confirms 260/260 IDs, exactly the two informational
status recoveries and one blocking render drift. The existing trust owner writer
also reissues its permitted source-bound JSON companion at `eed7a68e6`: all 369
nonbinding claim records and the 148-source population are preserved while the
changed runtime reader's identity/coordinates are rebound. Final guardrail import
acceptance and the protected ledger regeneration remain separate owner actions.
