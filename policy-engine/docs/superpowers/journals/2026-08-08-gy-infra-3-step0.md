---
research_only: true
authoritative_for:
  - diagnosis of the N10 provenance-stability drift at f9f25d408
  - one observer-inclusive, failed-path cold --check timing receipt
may_not_use_for:
  - implementation authorization
  - capability claims
  - owner appointment
  - automatic amendment of any plan
---

# GY-INFRA-3 Step 0 — N10 provenance drift diagnosis and cold-profile receipt

Task row: `GY-INFRA-3`, §3.5.7 (Rev 27),
[`docs/plans/active/layer3-slices/GY-engine-subordination.md`](../../plans/active/layer3-slices/GY-engine-subordination.md).

This is diagnosis and measurement only. No byte under `src/polisyos/**` or
`architecture/**` was changed; no governed artifact was reissued; no validation outcome was
weakened; and no Step 1 cache/consolidation work was started.

## Receipt and provenance rules

All load-bearing statements below carry one of the P37 labels:

| Label | Meaning in this journal |
| --- | --- |
| `recomputed` | Directly measured by the one observer, or arithmetic over those measurements. |
| `independently_reconciled` | Read and cross-checked from the pinned tree/history. |
| `consumer_asserted` | A boundary name/status emitted by the existing checker heartbeat. |
| `institutionally_supplied` | A frozen governed record or prior GY-INFRA-2 receipt. |
| `not_established` | Not reached, not emitted, or not safely inferable. It is never represented as zero. |

The supplied repository checkout began on `main` at
`f9f25d40837c2b9f30a9f3aeb814d31a4ee24447` with an unrelated modified file:
`policy-engine/src/polisyos/data_forge/read_api/catalog.py`. That file was not touched.
An isolated clean worktree was attached at
`/Users/deniskopylov/polisyos/.worktrees/gy-infra-3-step0` on
`codex/gy-infra-3-step0`, initially at the same pin. All evidence bearing on the conclusion was
read back in that worktree. This branch/worktree statement is `independently_reconciled`.

The ignored observer receipt is intentionally not a delivery artifact. Its own manifest carries
the same `research_only`, `authoritative_for`, and `may_not_use_for` refusal fields as this
journal. The receipt paths are under `policy-engine/tmp/gy-infra-3-step0/`, which is ignored.

## Result at a glance

- **Question A verdict — Case 3 (`independently_reconciled`):** this is neither a simple
  source-only stale capstone nor a proven producer recomputation defect. N8 recomputes its
  denominator over an ambient extension/runtime discovery set whose identity is not bound into
  its frozen record. N10a's `stage_gap_triage_drift` is a derivative validator projection of that
  N8 failure, not a separately established second-domain generation regression.
- **Question B receipt (`recomputed`):** the one exact cold `--check` ran for
  `297.938179666 s`, exit `1`, before an owner bundle returned. Nested N10 provenance stability
  took `174.321380875 s`, or `77.859031%` of the observed N10 capstone call. It returned
  `drifted`.
- **Healthy owner-build versus mode-work split (`not_established`):** N13b, projections, the
  post-derivation fence, owner-bundle return, warm cache-hit pass, and all work after owner return
  were not reached. There is no healthy cold profile in this receipt, so there is no measured
  shared-owner versus mode-work split.
- **§3 inference verdict — NARROWS, not supports (`recomputed` / `not_established`):** the
  failed route still has a dominant N10 stability segment, but it does not establish the proposed
  `840–950 s` shared build or any multi-mode payoff. It narrows the claim to a failure-path
  observation only and cannot authorize Step 1.

## Question A — static diagnosis before the lane

### What N8 actually compares

`tools/quality/validation/check_layer3_gy_value_gate_contract.py:3309-3330` loads the recorded
`payload["denominators"]` object and compares it with a fresh
`_catalog_denominators_cached()` value. The five compared members are:

1. `registered_method_count`
2. `catalog_entry_count`
3. `catalog_matches_registry`
4. `catalog_snapshot_id`
5. `catalog_snapshot_stable`

The recorded side at the pin is `389`, `389`, `true`,
`method_catalog_9483326427331f16`, and `true`, respectively
(`institutionally_supplied`; the frozen object has 11 keys). The current exact differing member
is **`not_established`**: the outer check reports only `closeout_worker_error`, and the supplied
prior receipt reports the aggregate `catalog_method_denominator_drift`, not a field-by-field delta.

The recomputed side is built at `:564-612`: a fresh registry calls
`ensure_all_methods_registered`, produces two catalog snapshots, and only establishes equality
between those two snapshots in the same process. It does not bind cross-process discovery inputs.
That construction is `recomputed` when the validator runs; its ability to identify the same
source set as a historical governed record is `not_established`.

The last commits touching the relevant recorded/comparison sides are:

| Side | Last touch at the pin | Interpretation | P37 label |
| --- | --- | --- | --- |
| N8 artifact | `369065e8` (2026-08-02) | Converged deployment receipt cascade; denominator values themselves changed in `3c16857f` from 390/390 + `method_catalog_3240…` to the current 389/389 + `method_catalog_948…`. | `independently_reconciled` for history; values are `institutionally_supplied` |
| N8 comparison code | `45dc1934` (2026-08-03) | The exact comparator above was read at the pin. | `independently_reconciled` |
| N10a validator | `45dc1934` (2026-08-03) | The cascade below was read at the pin. | `independently_reconciled` |
| N10 capstone adapter | `604b74e8` (2026-08-01) | Owns the recomputation call/fence wiring. | `independently_reconciled` |
| frozen N10a gap and trace | `c732eaa5` (2026-08-02) | Both carry the frozen `closed` status/receipt. | `independently_reconciled` |

The 3c rebaseline itself is a useful P37 witness: a complete `git diff --name-status`
enumeration over `pyproject.toml`, `core/components/discovery.py`, `foundry/extensions/**`, and
`foundry/methods/**` from `3c16857f..f9f25d408` found **0 paths** (path denominator `0`,
file-type denominator `0`). That is not evidence that the live discovery set is unchanged; it is
evidence that the declared repository source subset cannot explain or bind the denominator change.
It is `independently_reconciled`.

The broader architecture assertion supplied for main was also independently enumerated:
`git diff --name-only 4b9e76f20..109ba3f44` contains 146 paths (path denominator 146; file-type
denominator 146): 137 under `docs/research`, 5 under `docs/system-design-decisions`, 2 under
`docs/plans`, 1 under `docs/reference`, and `AGENTS.md`; 145 are `.md` and 1 is `.yaml`.
It contains 0 paths below `policy-engine/src/polisyos/` and 0 below
`policy-engine/architecture/policy_design_case/`. This is `independently_reconciled` and rules
out a stale branch explanation, not all ambient semantic inputs.

### Why the N8 predicate is ambient (P37)

`src/polisyos/foundry/methods/catalog/__init__.py:117-126` asks catalog registration to include
builtins, installed entry points, and a development scan. The latter reads
`POLISYOS_PACKS_PATHS` (`core/components/discovery.py:462-477`); entry points are discovered at
`:384-459`. Catalog snapshot identity includes entry/runtime posture
(`foundry/methods/catalog/snapshot.py:51-83,339-351`), which reaches installed package and
backend/dependency fingerprints. The frozen denominator object stores none of the entry-point
distribution identities, development-root bytes, or runtime/discovery manifest.

The observer saw `POLISYOS_PACKS_PATHS=null` in this process (`recomputed`), but that does not
freeze installed-entry-point or package/backend posture. The decisive premise for a cross-process
denominator equality is therefore `not_established`, while the ambient-input paths above are
`independently_reconciled`. This is P37: same-process snapshot stability is being used as if it
were a constructed cross-process provenance predicate.

### The N10a symptom has its own answer

`check_layer3_gy_second_domain_pack.py:5823-5841` makes
`_n8_transport_gap_closure` call N8 validation first. Any N8 validation issue makes that closure
`closed=False` with `n8_value_contract_invalid`. At `:5577-5643`, that in turn makes
`n8_transport_tuple_hardcode` expected `typed_residual`, and the validator compares both frozen
trace and gap statuses against it. The frozen gap and trace instead state `closed`, carry the same
`sha256:833c…` Stage-2 receipt, and bind the N8 hash `sha256:71e…`
(`institutionally_supplied`; the receipt/status consistency is `independently_reconciled`).

Thus the task-supplied prior path
`n8_owner_validation_failed: catalog_method_denominator_drift` followed by
`n10a_owner_validation_failed: stage_gap_triage_drift` at
`gap_id=n8_transport_tuple_hardcode` has a direct validator-level dependency. The valid Step 0
run independently re-established only the outer N10 result `drifted`; its parent/worker IPC
collapsed inner detail to `closeout_worker_error`. The exact live five-field N8 delta and exact
live inner N10a issue list remain `not_established` from this one receipt. No full N10a producer
recomputation occurred.

### Correct owner and smallest closure move (described, not performed)

The existing CODEOWNERS entries assign both `policy-engine/src/polisyos/foundry/**` and
`policy-engine/tools/**` to **`@DenisKopylov`**. The semantic owner is the Foundry
catalog/discovery boundary; the N8 tool is the producer/reissuer; the architecture record is
downstream. This identifies existing ownership only and is **not** an owner appointment.

The smallest correct closure is: first have that boundary produce and bind a controlled discovery
manifest (entry-point distribution identities, development-scan roots and bytes, and relevant
runtime/backend package identity), failing closed on an unbound ambient input. Then rederive and
reissue N8, and only then reissue the dependent N10a trace/gap records. Do not reissue N10a alone,
edit a count, or hard-code this machine's discovery result. This is a recommendation for a
separately authorized repair, not an implementation authorization.

## Question B — one cold-process observer receipt

### Budget, observer, and environment

`report-timing --output-format json --include-unmeasured --limit 22` reported the check lane's
two prior samples as `898666.254 ms` and `951000.0 ms`, a p95 of `951000.0 ms`, and a recommended
timeout of `1902000.0 ms` (31m42s). The samples/p95 are prior
`institutionally_supplied` evidence; the 2× arithmetic is `recomputed`. Sixteen of the 22 lanes
have one sample, where p95 is merely that sample; this particular check lane has two samples.

The exact executed lane was, once only:

```text
.venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --check
```

The ignored, standard-library-only observer launched precisely that command with a 1902-second
deadline; it did not change arguments, return values, cache behavior, artifacts, or validation
logic. A lazy `sitecustomize` hook timed the named adapter functions and nested
`check_provenance_stability`; raw stdout/stderr were copied unchanged. That makes elapsed intervals
`recomputed`; the checker's textual heartbeat labels are `consumer_asserted`. Observer overhead
relative to an uninstrumented historical run is `not_established`, so the figures are explicitly
observer-inclusive.

The isolation-local virtual environment was provisioned by copying the already-present local
environment after the requested offline sync could not acquire cached `jaxlib==0.8.2`. Its
interpreter prefix and imported PolicyOS source resolved in the target worktree. That verifies
interpreter/source locality (`independently_reconciled`), not equality to the historical
environment (`not_established`). `production_data` was exposed only through an ignored symlink;
the catalog path opens its database read-only, but filesystem immutability of the symlink target is
only `institutionally_supplied`.

### Command ledger and non-receipts

Durations are the launcher-reported wall time; static source/history batches are read-only and
were all below 1.4 seconds. Each multi-query row is one shell invocation containing the named
read-only commands. Except for the explicitly prior timing-catalog figures in row 5, every local
wall/exit value in this table is `recomputed` from its launcher receipt. No listed
setup/preflight invocation entered a completed lane.

| # | Command or command batch | Wall / exit | Receipt |
| --- | --- | --- | --- |
| 1 | `git status -sb`, `git rev-parse`, `git diff --numstat` in the supplied checkout | `0.1 s`, 0 | Detected the unrelated main-tree edit; `independently_reconciled`. |
| 2 | `sed`/`rg` reads of `CONTRIBUTING.md`, P37 register, and GY §3.5.7 | `0.1–0.2 s`, 0 | Instruction/plan reads; `institutionally_supplied`. |
| 3 | `git worktree add -b codex/gy-infra-3-step0 … f9f25d408` and target `git status -sb` | `1.8 s`, 0 | Clean attached target; `independently_reconciled`. |
| 4 | `rg`, `nl`, Python JSON walks, `git show`, `git log`, `git diff --name-status` over the N8/N10a comparator, artifacts, catalog/discovery sources, and history | `0.1–1.4 s` per read-only batch, 0 | Static diagnosis above; `independently_reconciled` except frozen values. |
| 5 | `python -m tools.cli report-timing --output-format json --include-unmeasured --limit 22` | `1.2 s`, 0 | Budget preflight; catalog values `institutionally_supplied`. |
| 6 | Create ignored `production_data` symlink; target/locality checks | `<0.1 s`, 0 | Setup only; no governed path changed. |
| 7 | `uv sync --frozen --offline --extra lint --extra test --extra runtime --extra solvers` | `0.7 s`, 1 | Honest setup non-receipt: cached `jaxlib==0.8.2` absent. |
| 8 | Ignored observer source creation (`sitecustomize.py`, `observe_check.py`), `py_compile`, and target-prefix checks | `<0.2 s` each, 0 | Observer only; no producer edit. |
| 9 | First observer launch with an incorrect observer path | `0.032680917 s`, 2 | Non-receipt: Python could not open the checker at the incorrect path; no worker/events. |
| 10 | Main-environment interpreter/locality preflight and launch | `30.556 s`, 1 | Non-receipt: the validator rejected the wrong interpreter/check-out identity before intended measurement. |
| 11 | Move failed ignored stub venv to ignored scratch; copy local environment into target `.venv`; target-prefix/import check | `28.77 s` for copy; checks `<1.3 s`, 0 | Environment preparation only; source locality verified. |
| 12 | **Exact target command above, via observer, deadline 1902 s** | **`297.938179666 s`, 1, no timeout** | **The sole valid lane receipt.** |
| 13 | `rg`/hash/WC readback of raw streams and observer JSON; timing arithmetic; final history/census/owner readbacks | `0.1–0.5 s` per read-only batch, 0 | Evidence reconciliation; `recomputed` where arithmetic. |

Rows 9 and 10 are preserved as non-receipts, not timing samples and not retries of a completed
lane. Row 12 is the one planned expensive attempt; it was not rerun after the failed result.

The raw receipt is retained only in ignored scratch:

| File | SHA-256 / size | P37 label |
| --- | --- | --- |
| `manifest.json` | `71e2978ecc01e581953776648d3588e4d8162c653d1a40def09c77a0913f3818` / 8,005 B | `recomputed` observer record |
| `events.jsonl` | `2d868a8fa919f3c5a5eefaf6c4a9a568c35c0357312f0d6b59d16515b545e8e9` / 1,663 B | `recomputed` observer record |
| `checker.stdout` | `d5c57abf3fbc252f503fd2b8ca4c3c39a462b96e523fb534ba09993d23bbcb6f` / 258,314 B | raw evidence; inner cause unavailable through parent IPC |
| `checker.stderr` | `83575c8f3f15c38241123247dc7c2f48d7a1cfc460194611a82a7a7da98b4bc3` / 3,523 B | raw evidence |
| `direct-entry-timing.jsonl` | `e6f3f7bf45db48e55a486c41d900616ae5b318331d2a6cc8f77b4b35ea6190b1` / 268 B | `recomputed` direct-entry receipt |

### Stage profile — failed cold path, not a healthy profile

The complete process wall is `297.938179666 s` (`recomputed`). The owner bundle did not return,
so a full owner-load denominator is **`not_established`**. To avoid treating a partial path as a
healthy owner load, the table shows an additional, explicitly non-additive partial-route denominator
of `224.835834208 s` (pre-fence plus the failed N10 capstone call). Nested rows are not summed with
their parent.

| Stage | Wall time | Share of full owner load | Share of partial route / parent | Share of total process | P37 / outcome |
| --- | ---: | --- | ---: | ---: | --- |
| pre-derivation `_owner_cache_fence` | 0.942242375 s | `not_established` | 0.419080% partial route | 0.316254% | `recomputed`; completed. Heartbeat boundary name is `consumer_asserted`. |
| `_recompute_n10_capstone` | 223.893591833 s | `not_established` | 99.580920% partial route | 75.147667% | `recomputed`; raised `OwnerProjectionError`. |
| nested `check_provenance_stability` | 174.321380875 s | `not_established` | 77.532739% partial route; **77.859031% of N10** | 58.509245% | `recomputed`; returned `drifted`. |
| nested `_derive_provenance_stability` | 174.191027875 s | `not_established` | 77.474762% partial route; 99.925223% of stability | 58.465494% | `recomputed`; returned `drifted`. |
| N10 capstone outside nested stability | 49.572210958 s | `not_established` | 22.048181% partial route | 16.638422% | `recomputed` subtraction; no narrower component attribution is established. |
| `_recompute_n13b_contract` | — | `not_established` | `not_established` | `not_established` | Not reached; **not zero**. |
| `_project_n10` | — | `not_established` | `not_established` | `not_established` | Not reached; **not zero**. |
| `_project_n13b` | — | `not_established` | `not_established` | `not_established` | Not reached; **not zero**. |
| post-derivation `_owner_cache_fence` | — | `not_established` | `not_established` | `not_established` | Not reached; **not zero**. |
| owner bundle return / cache-hit repeat | — | `not_established` | `not_established` | `not_established` | Not reached; **not zero**. |
| everything after owner bundle return (mode-specific work) | — | `not_established` | `not_established` | `not_established` | Not reached; **not zero**. |

The unassigned process remainder is `73.102345458 s` (`24.536078%` of total,
`recomputed`). It includes startup, parent/worker handling, and failure cleanup; it is **not**
mode-specific work. Its finer allocation is `not_established`.

**Owner-build versus mode-work result:** owner build = **`not_established`**; mode-specific work =
**`not_established`**; healthy total = **`not_established`**. No zero, interpolation, or historic
single-lane attribution has been substituted for those values.

N10 provenance stability remains dominant *within this failed N10 call* (`77.859031%`,
`recomputed`). That is not a claim about a healthy completed owner build. The observer-inclusive
duration also must not be compared numerically with the supplied prior receipt without an
environment/observer equivalence proof, which is `not_established`.

## Decision on §3 and Step 1

The §3 fixed-cost inference is **NARROWED**. The receipt supports the smaller statement that
provenance stability dominates the failed N10 route, not the larger statement that a healthy
completed owner bundle dominates all six modes. The architect's `840–950 s` shared-cost range,
the `18–25 min` consolidated-cycle expectation, and the historical `~2,258 s` single-lane
attribution remain prior evidence only (`institutionally_supplied`) and are not replacement
measurements. The proposed healthy split is `not_established`.

**Step 1 recommendation:** do not build mode consolidation now. First close the P37 discovery
provenance issue, reissue N8 and then N10a under the responsible existing owner, and repeat this
Step 0 profile on a healthy path. The sole valid run never returned the owner bundle or produced a
cache hit, so no normal mode is observed consolidatable and shared state beyond the checker's
explicit cold cache clear is `not_established`. `--corrupt-field-drift-check` and
`--source-flip-mutations` mutate, and `--cold-rederive` is cold by name; all three should remain
separate processes unless a later, separately authorized equivalence proof says otherwise. This
is a stop/report decision, not a claim that consolidation can never be worthwhile.

## Fence recheck before delivery

Before this journal was written, `git diff --exit-code -- policy-engine/src/polisyos/
policy-engine/architecture/` returned 0 in the isolated worktree (`independently_reconciled`).
The only intended delivery path is this research-only journal. Commit/readback status is recorded
after the branch write; no state claim is made here from staging alone.
