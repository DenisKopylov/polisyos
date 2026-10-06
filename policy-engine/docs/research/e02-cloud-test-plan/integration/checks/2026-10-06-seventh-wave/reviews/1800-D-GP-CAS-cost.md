# D GP / CAS / B1.1 ledger review

## Scope and immutable pins

Read the repository instructions, the E02 handoff, the execution-organization guide, and the result-pack integrity receipt. `import_results.py --check` passed; `verification.json` was checked; the required failures-only query and targeted B120/B158/B159 lookups were run. The historical result-pack routes remain compact candidate evidence, not semantic closure: all three findings route as `partial`, with semantic adequacy `not_established`.

`R/1740-new-head-triage.json` and `R/after-checkpoint11-ref-delta.json` bind the current remote refs, exact previous tips, and trees. Each previous tip is an ancestor and each local remote-tracking ref matches its pinned head:

| D ref | Previous tip | Candidate | Candidate tree |
|---|---|---|---|
| published-root | `9cfe108376df509cbfd6edd7fd0d7e24e3dd277d` | `3c636ff52718897c9900a49580c9bd058086de35` | `a5a74887e96020550b27b35ac5ceaa65e43ec0e5` |
| published-oracle | `7d7b35876400a7b9a35e47f178e0dcdf158c9d00` | `c40e633fc01398cdf757f3361f6e1ed0d62497ab` | `1747e87c1052e821b2c077873143fe82dce0b5a9` |
| published-funnel | `d212314677ed2a6af8021350ec135e568db719d7` | `1159cad1c970c783b30c943cf2eb38b61265f48d` | `6152c1f618920e6a5985ab475424fd836210bdf6` |
| published-transfer | `cc87e523f0e8cf2ded2283ce8680d018e8a10bd0` | `4fff9e8089bfba442e2ec8710cda45bfd9b6959c` | `e4535a868e0b83be2ccacd886fa6b7852caab9a2` |

These refs are parallel inputs, not one assembled candidate. Do not union their receipts as if they were a single tested tree.

## GP numerical evidence

The old 23-case evidence at `243ca4e04d6fcb2cbe8c9494e68f06c75fe749a3` remains source-qualified to that source. A later independent `gp-profile4` run improves coverage: its report records PASS for the unchanged 23-case analytic profile at source `d38f94c8a8095abb00052b8e78f7b8a470453ed4`, test commit `18699ce536fca6ce174ff1caf1435a79912f0920`, test SHA-256 `95bb5e2137d807bd3d005c27b240c8b1d86d7ccffc65a3da045721fc55d79265`. The independent numerical oracle uses saved fitted scalar parameters and dense NumPy conditioning; this is meaningful bounded evidence, not optimization-quality or full finding closure.

That 23-case receipt does not transfer as an exact pass to root `3c636ff`. Its `candidate-origins.json` enumerates 857 loaded origins; comparing the full set with root gives 826 exact hashes and 31 mismatches. Among direct test inputs, `SearchSpace` and `Evaluation/StrategyState` code changed (`space.py`, `types.py`), and the test file itself changed after the recorded test commit. The Bayesian strategy and generator retain the d38 blobs, but the changed input types and test source require one bounded rerun on the frozen integrated source before claiming current 23-case coverage.

The extended 87-case profile remains UNRUN. The recorded `startup01-result.json` says pytest never started because its referenced prior path was missing; the 23-case run does not stand in for it. Do not report extended restore/cadence/RNG evidence as pass.

## CAS snapshot and consumers

The B-owned CAS dependency at `72235911a7a48cd0c0cf401c2b055a8d31907c2f` / tree `6dd300a6b33b31a4b24ba231af4e0fb60065b81e` has a complete 9/9 native FileSystemCAS receipt, including separate-process special-path refusals. The D receipt lists 13 B owner files; all 13 blobs match the exact current root and transfer candidates. This bounded B API evidence can be carried. It does not close D consumers.

- **Vector receiving process:** `transfer-vector-second-process.json` records two process tests and the 60-case native suite PASS at d9, with vector sources/tests byte-identical through cba and a separate 68-case cba run covering the intervening transfer strategy delta. The receipt explicitly does not call this a fresh all-source replay on cba. Root `3c636ff` has the cba vector/source blobs, so this is bounded source-carry evidence there. Transfer `4fff9e8` changes `vector_memory.py` and `strategies/transfer.py` after cba; the second-process consumer needs a delta rerun on that head or the final frozen merge.
- **Champion and served SearchService:** `native-service-correction.json` records 58/58 tests at source `6b5195b5400ce10f5ed72e952a368648f0cc7ac9`, including fresh public resume and one-public-snapshot/no-split-read cases. The current root changed `search/service.py` by 234 lines and its persistence tests by 249 lines after 6b. Therefore the 58-pass output is not exact evidence for root `3c636ff`; rerun the affected service consumer on the frozen source. The old receipt itself limits authority and deployment claims.

Thus the prior “three CAS consumers UNRUN” label is too coarse: the B snapshot API is verified, the vector edge has bounded source-carried evidence at root, and the service edge has a real earlier positive run. Neither the modified transfer head nor the modified current service source has a fresh exact combined receipt.

## B1.1 settlement, cost intake, and split calls

The D `B-dependency.json` adopts the canonical B implementation: all 18 listed owner-file blobs match the current root/funnel/transfer source. The ledger/middleware files are byte-identical to B source `1015b9f3e24d8759f82c73d2cbd9d5b1f6a0e786`; the producer settlement/enforcer files are byte-identical to `562ca2c25ca68fd90c4d5225b1b33fdd5b161940`. Keep one B ledger; do not add a D duplicate.

The B1.1 ledger persists a receipt binding `event_id`, `payload_digest`, budget key, amount, provider, and revision. Exact retries return the original receipt, conflicting reuse of an event ID refuses, and filesystem publication failure remains unknown until resolve/retry. The producer event binds request/response digests, provider/model, amount, and cost origin. This is sound bounded local idempotency and settlement evidence. It does **not** persist `run_id` or `evaluation_id` in the receipt: the enforcer strips underscore-prefixed call metadata before producer invocation, and its event/request digest does not include `_evaluation_id`. Run IDs appear in audit/scope handling, not as a durable receipt field. Current root's revised response-text test checks canonical `spend_receipts`, provider, key, digest, and amount, but does not establish evaluation attribution or a stable caller-owned attempt identity.

FUN-01’s “split” is Stage A/B API continuation, not a requirement for a second budget ledger or automatically for a multi-key atomic transaction. Its criterion requires the same permitted stage work, actual expenses, and stop reasons for equivalent full and split calls, with changed-input differences preserved. The earlier `34cd` run did include `test_native_policy_callers_full_split_actual_events_and_fresh_reopen` and a 156/156 affected suite. However, after that run, root changed the funnel orchestrator by 147 lines, response intake by 155 lines, and the funnel test file by 113 lines. Those changes add unknown-ack receipt readback, replay detection, and recorded-spend projections, directly changing the measured consumer. Rerun full/split parity and fresh B1.1 reopen once on the frozen integration source. Only require multi-key atomicity if the actual configured full/split profile uses multiple budget keys; the current focused response-text fixture configures only `run`.

The raw HTTP numeric property is still broken. The canonical Gateway client blob `52005eecef61a6ed0b727a7a444e28cf3acfa1e4` is unchanged from the recorded red source through root, funnel, and transfer; `_post_json` still uses plain `json.loads` (no Decimal `parse_float`). Consequently `1e-1000` arrives as `0.0`, and `-1e-1000` as `-0.0`; the strict cost guard cannot reconstruct the lost sign/magnitude and accepts them as zero. This is the divergent case the gate exists to reject. The older exact response-text run recorded 21 failures / 3 genuine zero/paid controls passing; its fresh-ledger witness recorded positive underflow as a zero settlement. That receipt used the earlier D1.0 ledger. The current root has a corrected B1.1 assertion shape but no run output for its revised test, so do not transfer the old persisted-ledger result to B1.1. The exact current source still makes the new test’s raw-lexeme assertion fail.

The smallest corrective move is in the canonical B Gateway decoder: preserve JSON numeric lexemes through intake (e.g. Decimal parsing), then validate every declared total/alternate/component before selecting a reported cost. Keep true zero distinct from signed/nonzero underflow, and make the D consumer read the B1.1 receipt after a fresh reopen. Re-run the new actual-`response.text` test, then the affected full/split consumer against that same frozen source. No secondary D ledger is needed.

## Review disposition

- **GO, bounded:** B-owned CAS public snapshot mechanism (9/9, exact 13-file carry); B1.1 durable idempotent settlement source/owner contract (exact 18-file carry).
- **Limited carry:** GP 23-case result only at d38, not current root; vector second-process evidence at d9/cba lineage only where exact source deltas remain supported.
- **HOLD for current closure claims:** GP 23 on root, GP extended 87, champion/service consumer on root, vector consumer after 4fff’s source delta, current full/split consumer after funnel changes, and HTTP text-cost intake. The HTTP underflow remains a concrete source defect. Treat B120/B158/B159 as open/partial until canonical decoder repair and exact frozen consumer receipts exist.

No tests were run in this review. Only this ignored report was written; no source, tracked handoff, environment, or ref was changed.
