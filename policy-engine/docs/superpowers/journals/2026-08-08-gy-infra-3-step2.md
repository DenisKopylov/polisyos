---
research_only: true
authoritative_for:
  - design and verification record for the GY-INFRA-3 Step 2 E11 scheduling gate only
may_not_use_for:
  - implementation authorization
  - capability claims
  - owner appointment
  - automatic amendment of any plan
---

# GY-INFRA-3 Step 2 — E11 enforceability journal

Task: `GY-INFRA-3`, Step 2, E11 in
`docs/plans/active/layer3-slices/GY-engine-subordination.md` §3.5.7 Rev 28.

## Scope and outcome

This change adds `tools/quality/testing/review_freeze.py`, a lane-local E11 scheduling bridge. It
does not create another package renderer: full and delta bytes continue to be rendered by the
existing `tools/quality/testing/build_review_package.py`. It is deliberately a direct script, not
a unified-tools registration and not a replay-producer interlock. Capability state after this
change: `implemented_but_not_orchestrated` — a lane can enforce its own E11 transcript, but no
GY producer has yet been wired to require it. That limitation is `not_established` as a
programme-wide enforcement claim.

The source, governed-artifact, and expensive-validator fences were preserved. The task does not
touch GY-DEF6, reissue N8/N10a, run a GY lane, run a replay, or alter
`src/polisyos/**` or `architecture/**`. Those negative scope statements are
`independently_reconciled` from the final changed-path readback after the edit and before commit;
they are not claims about any other worktree.

Historical motivation — E11's reported `17/36` receipt-churn commits, approximately `47%`, and
the reported approximately `1 h 37 m` closeout cost — is `institutionally_supplied` by the Rev 28
plan. This step does not recompute those historical figures.

## Design decisions

### Minimal boundary and existing owner

The implementation is adjacent to the existing packager, under
`tools/quality/testing/`, and calls its public builder rather than duplicating package format,
Git hardening, timing, or review rendering. Delta handoff is raw checklist bytes plus their
digest; the existing packager continues to treat those bytes as opaque. The checklist renderer is
only the missing bridge from open E11 batch members to the existing `--prior-findings` input.

The ledger is a fixed, append-only JSONL transcript at `.e11/<lane>.ledger`, rather than an
arbitrary user-selected pathname. This prevents a lane with an open blocking batch from declaring
a parallel empty transcript. The ledger is a narrow lane-local scheduling record, not a general
chronology owner or a claim of automated repository-wide enforcement. This P13 narrowing is
`recomputed` from the implementation surface: there is no registry entry, producer hook, or
global scan.

### Freeze identity deliberately differs from E12

The source identity is a recomputed Git-tree fingerprint over all tracked implementation paths.
For this repository layout, the implementation root is `policy-engine/`; its `docs/` and
`architecture/` subtrees are excluded, as are the exact ledger and the ledger's transient lock.
No caller-supplied receipt path is accepted as an exclusion. A fixture proof asserts the
product-root selection and its file-type/path behaviour. This identity choice is `recomputed`.

E12's import closure answers “what bytes define this governed artifact?” E11 instead answers
“has the implementation reviewed at this freeze changed?” Applying E12 automatically would bind
the wrong question. This source fingerprint intentionally does **not** establish ignored or
untracked ambient inputs, the runtime environment, documentation semantics, governed-artifact
semantics, reviewer independence, review completeness, receipt-chain membership, or receipt
semantic validity. Each of those omissions is `not_established` unless a later consumer supplies
independent evidence.

The source comparison fails closed for staged, unstaged, and nonignored-untracked source changes;
for assume-unchanged and skip-worktree index flags; and for unsafe effective Git freshness
configuration (`core.filemode`, `core.trustctime`, `core.checkStat`, `core.fsmonitor`, and
`core.ignorestat`). Effective configuration, including linked-worktree settings, is read through
the hardened Git context. The comparison and its failure conditions are `recomputed`; the
assumption that Git's remaining default-stat configuration is adequate is deliberately bounded to
that constructed procedure, not an environmental capability claim.

### Conservative classifier and replay state

The only initial `debt` route is an exactly re-run, byte-bound Ruff safe `I001` diagnostic.
Human labels such as docstring, naming, style, or “cosmetic” remain
`institutionally_supplied`/`consumer_asserted` and produce `batch`; absent or malformed evidence
is `not_established` and also produces `batch`. This is a deliberate P13 narrowing of E11's
example list, not a claim that the tool can determine general semantic harmlessness.

`replayed` and `closed` are scheduling-ledger states only. They carry
`state_scope=e11_scheduling_ledger_only`,
`state_claim_grade=degraded_institutional_scheduling_record`, and
`state_semantic_validity=not_established`. The tool content-binds an already committed receipt but
cannot establish receipt semantics, receipt-chain membership, reviewer independence, or repair
acceptance. No positive lifecycle word is allowed to conceal that degradation.

## Predicate provenance (P37)

| Predicate or conclusion | Admission label | Gate behaviour |
| --- | --- | --- |
| Ledger hash chain, semantic state transitions, canonical lane path, source fingerprint, current source match, index/config checks, batch membership, checklist bytes, package/result/receipt digests | `recomputed` | Rebuilt at every consuming transition; drift refuses the transition. |
| Git history prefix and committed-marker presence | `independently_reconciled` | A live rewrite, deletion, or uncommitted gate event fails validation/authority. |
| Lane name, receipt-chain identifier, review baseline, and raw finding semantics | `consumer_asserted` | Bound and visible, but cannot authorize `debt`; chain identity cannot upgrade replay semantics. |
| Reviewer roster, reviewer identity/independence, review completeness, and repair acceptance | `institutionally_supplied` | Roster presence is mechanically checked; the irreducible claims remain only degraded scheduling evidence. |
| Receipt-chain membership and receipt semantic validity | `not_established` | Receipt bytes must be present and committed, but resulting replay/close state remains explicitly degraded. |
| Missing classifier output, malformed evidence, unknown class, failed byte binding, unavailable review evidence | `not_established` | Conservative `batch` or refusal; never `debt`. |

The required falsify-the-declaration probe is behavioral: a genuinely blocking raw finding is
declared `cosmetic`/`recomputed`/`ruff_i001_v1`, with the declaration markers retained. The real
ledger semantic replay re-runs Ruff and rejects the forged debt. Its result is `recomputed`.

## State-machine and evidence safeguards

- A freeze marker, package binding, reviewer result, resolution, replay record, and close record
  must be committed before it becomes authoritative for the next gate. The live suffix is reported
  as pending rather than projected into the committed lifecycle. `independently_reconciled`.
- The state machine replays every committed event and rejects self-hashed but causally impossible
  admissions, replay records, provenance maps, terminal-state additions, wrong canonical ledger
  paths, and forged source scope. `recomputed`.
- A full review range is bound to the opening review base and cannot be empty. A successor delta
  range is bound to its predecessor freeze source and must carry every unresolved predecessor
  member. `recomputed`.
- Every required reviewer of a successor must consume the successor delta, not a convenient full
  package; every carried member must be resolvable from that delta. `recomputed`.
- The semantic transcript reconstructs the exact checklist from carried raw finding bytes and
  compares it to the bytes sent to the existing packager. Member metadata adjacent to arbitrary
  opaque prior-findings bytes is insufficient. `recomputed`.
- A close rechecks the active freeze source; source movement after a replay record refuses close.
  `recomputed`.

## Behavioral verification

The focused E11 suite contains **46** test functions, counted by
`rg -n '^def test_' tests/repo_quality/tools/test_review_freeze.py | wc -l`
(`recomputed`). The complete focused run passed all 46 (`recomputed`, observer wall
approximately `298.7 s`; the duration is an observer sum, not a timing-budget sample).

The behavioral witnesses include the eight required E11 worlds plus adversarial variants:

- unfrozen → `fix_now`; frozen blocking → `batch` and replay refusal; re-run I001 → `debt`;
  unknown class → `batch`; and false-cosmetic declaration → `batch` (`recomputed`);
- committed-marker requirement, exact source movement, empty batch, open member replay refusal,
  append-only successor, second-lane isolation, nonexistent commit, and canonical lane-ledger
  rejection (`recomputed`);
- malformed provenance, forged debt/replay/close/post-close events, forged source scope,
  uncommitted replay, tampered package/result/receipt, a fake I001 record with cosmetic markers,
  and a forged delta checklist (`recomputed`);
- assume-unchanged, filemode disabled, and Git boolean synonym (`core.trustctime=no`) source
  probes; hostile Git context; product-root source-scope fixture; empty/full and wrong-base range
  probes; docs-only successor; source movement after replay; and successor roster coverage by a
  real delta (`recomputed`).

These execute the real record, real gate, canonical packager, Git objects, and byte bindings. They
do not merely inspect marker fields, satisfying P29/P32/P33 for the implemented boundary.

## Command record and receipts

Durations below are tool-observed wall time. A “less than 1 s” static inspection was a read-only
`rg`/`sed`/`git` inquiry; it is `independently_reconciled` only for the cited path or branch state,
not a broader census.

| Command / action | Result | Duration and provenance |
| --- | --- | --- |
| `git status -sb`, branch/root readback in the target worktree | Attached to `codex/gy-infra-3-step2`; only README plus the new tool/test were modified before the journal. | `0.2 s`, `independently_reconciled` |
| Static review of E11, failure register, existing packager, tool registry, tests, and Git helper seams via `rg`/`sed` | Existing packager owns canonical full/delta bytes; direct tool avoids a new registry surface. | individual reads `<1 s`, `independently_reconciled` |
| Initial red-first E11 test development | The absent/new API witnesses failed (first broad run: `16` failures); a later hardening selection had `3` expected failures. | `not_established` duration for the first inherited development receipt; `4.26 s`, `recomputed`, for the later five-test selection |
| Focused hardening selections: Ruff format/check plus targeted E11 pytest selections | All selected worlds passed after the repairs, including P37, source-scope, alternate-ledger, stale-close, successor-delta, and fake-checklist probes. | approximately `58 s`, `recomputed` |
| `.venv/bin/python -m pytest -q tests/repo_quality/tools/test_review_freeze.py` | All `46` focused tests passed. | approximately `298.7 s`, `recomputed` observer wall |
| `.venv/bin/python -m pytest -q tests/repo_quality/tools/test_review_package.py` | All `26` canonical-packager importer tests passed. | approximately `31.1 s`, `recomputed` observer wall |
| `.venv/bin/python -m ruff check ...`; `.venv/bin/python -m ruff format --check ...`; `py_compile`; `git diff --check` | Passed. | `2.1 s` combined final static receipt, `recomputed` |
| `python3 policy-engine/tools/quality/testing/review_freeze.py --help` from worktree root | Direct documented entrypoint imports and renders help. | `0.3 s`, `recomputed` |
| `polisyos-tools architecture guardrails check` | Exit `1`; see non-receipt below. | approximately `41.5 s`, `recomputed` |
| Final changed-path check: `git diff --name-only -- policy-engine/src/polisyos policy-engine/architecture` | Empty output: this task did not change either fenced path. | `0.3 s`, `independently_reconciled` |

## Honest non-receipts and limitations

- Architecture guardrails returned exit `1` because the existing deep-import baseline differs from
  runtime HTTP imports in `execution_policy.py`, `routes/runs.py`, `channel_contracts.py`,
  `lex_pipeline.py`, and `lex_search_projection.py`. The changed-path check above is empty for
  `src/polisyos` and `architecture`, so this receipt is `not_established` as a Step 2 regression.
  No baseline sync was performed because that would violate the fence.
- The first direct `python3 tools/quality/testing/review_freeze.py --help` attempt failed with
  `ModuleNotFoundError: tools`; the standalone path bootstrap was then added, and the documented
  worktree-root command passed. The first attempt is an honest `not_established` usage receipt;
  the later one is `recomputed`.
- An exploratory `uv run python -m ruff --version` created an ignored partial worktree `.venv` and
  did not provide Ruff there. It is not used as verification (`not_established`). The system
  `python3 -m ruff --version` reported `ruff 0.15.0` (`recomputed`).
- No expensive GY validator lane, full closeout, source replay, full backend suite, or CI-parity
  suite was run. That is an intentional fence observance, not an availability claim. Their results
  for this task are `not_established`.

## Operator handoff

From the repository worktree root, use the README commands in
`tools/quality/testing/README.md`: open and commit `.e11/<lane>.ledger`; freeze and commit it;
build the full package through the existing packager bridge; commit a content-bound result for each
reviewer; disposition findings; build a successor delta checklist/package before resolving carried
members; commit the resolution records; then record a pre-committed receipt and commit the
degraded replay/close scheduling events. `--prior-findings` receives the raw exported checklist
unchanged. The gate refuses an open batch, stale source, uncommitted authority event, bad byte
binding, unsupported cosmetics, or an incomplete successor delta review.

No command in this journal appoints an owner, authorizes GY-DEF6 implementation, declares a
receipt chain semantically valid, or automatically amends a plan.
