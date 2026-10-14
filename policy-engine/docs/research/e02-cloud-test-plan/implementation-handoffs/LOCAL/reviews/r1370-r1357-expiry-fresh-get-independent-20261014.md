# R1370 — independent review of the R1357 TTL-expiry/fresh-GET candidate

**Verdict: GO for root’s focused composed replay, with the removal control still required.** This is a bounded review of a virtual test-only candidate. The candidate is unapplied and unrun; this is not a runtime pass, billing validation, or formal closure (`closure_ids=[]`).

## Bound inputs and current source

- Candidate patch: `raw/r1357-r3-expiry-fresh-get-candidate-20261014/candidate_test.patch` @ `833347e227dc962dcc4cfb6a4ae08550acb14ed9e4635913b9145083167ebf5c`.
- Manifest: `.../manifest.json` @ `b7577e4172dc53f4e5021dbda8767c82abf7b7841d76bc5699f0dc5784ea7d92`; author readback: `.../static-readback.json` @ `713261fe6cb6b84d617ee04b0b00d785f1e71949cbc015f2a37c58fba64a744a`.
- Original-criteria audit: `raw/r1341-r3-monetary-whole-property-audit-20261014/review-r1341.md` @ `c03bd385160d6966a017e46c957f3b09fddb6fea284154abe99941a192ce28ba`; machine record @ `901fbea7a9242975c651e500dfe4d243d782cc50dabfa1401279e5feffcd6393`; its 30-path source binding @ `ccfb83bd320443eed9a2fedabf1d3e13624a3dac8401e89a040a4f7af198c4a5`.
- Current source frame: `root-author-source-frame-r1371-20261014.json` @ `0b6eed59afa437cebdad6b2dacdd4ffed9d15316edeb7dac2828faeac609ddb5`. Readback reports Source38, 623 source paths, clean frame, and no acceptance/closure.
- Current checkout is branch `codex/e02-unified-local-20261009`, HEAD `1387e46f4a2f9e4f95cdc17ca5d7e31f8e506974`, tree `01f8ef015bd60ca4115b9d19435ebd53f1f3f26e`, parent `3d03c1e4cc1e686983f0def199465dd801457991`. The R1341 source binding still matches all 30 current files; the 10 paths changed since R1357’s older source HEAD do not intersect those 30. The target test remains byte-identical to its candidate preimage: `test_nl_pipeline_cost_projection.py` @ `d85790cd89d335dcde5839323277bbe8449c7283a4c8ed80c5106b0312be848d`.

Independent replay parsed both unified-diff hunks against that exact test preimage in memory. The reconstructed 51,933-byte candidate has SHA-256 `53b78c322aec4b11ccbfa1346aa4ab5ca15c981135e3f09eeaa372f70a9c1e8b`, matching the manifest; Python AST parsing succeeds. `git apply --check --verbose` also exits 0 for the one test path. No patch application, source/index/history write, product import, or test execution was performed.

## What the candidate actually exercises

The added block follows the ordinary NL POST’s persisted job/run binding and uses the real `InMemoryPromptCache`, `CachingLLMClient`, `TracedLLMClient`, `BudgetMiddleware`, and `FileBudgetLedger` classes with a deterministic simulated provider. The provider is explicitly local and synthetic.

The source behavior supports the test’s discriminator: `InMemoryPromptCache.put` stores a monotonic expiry; `get` deletes an expired entry and increments both `expired` and `misses`; `CachingLLMClient` routes the subsequent miss through provider settlement hooks. For the chosen same request, the assertions distinguish one provider call, one cache-reuse event linked to the first provider event, then a second provider call after sleeping past the 0.5-second test TTL. The wrapper’s controlled cost sequence makes the first call reported zero and the post-expiry call missing raw cost; the simulated response carries positive token usage, and `TracedLLMClient` classifies that case as estimated rather than zero or unknown.

The durable portion is also source-grounded. `FileBudgetLedger.list_producer_events_for_run` reloads the persisted snapshot and filters by exact typed run binding. The candidate constructs a second `BudgetMiddleware`/`FileBudgetLedger` reader over the same ledger file, checks the same owner identity, attaches that reader to the existing `DebugService`, then calls the real `/api/v1/runs/{run_id}/agents` GET. It compares the full selected-owner event set and each material event field, including the pending event, while retaining the same-cost foreign-ControlJob exclusion and tampered-run refusal controls. The debug service permits rebinding only when the ledger owner identity matches; the API route reads through the same runtime API context’s `debug` service.

The direct property assertions are behavioral rather than marker checks: provider call count, cache counters, event identity/linkage, cost-origin/amount distinctions, durable acknowledgements, exact persisted binding, a separate ledger reader, and a public GET projection are all checked. The manifest’s removal falsifier is apt: removing the cache expiry check while retaining telemetry markers should leave provider calls at one, expiry count at zero, and omit the second provider settlement. That falsifier is **UNRUN**, so the composed native replay must run it before anyone treats the test as a completed P29 proof.

## Original criteria remain separate

| Criterion | R1357 contribution | Current state |
|---|---|---|
| B10 / ordinal 10 | Does not exercise the high-score unavailable-input candidate followed by a valid second candidate. | `UNRUN / not_established / not_adjudicated` |
| B66 / ordinal 192 | Adds a proposed local miss → reuse → real TTL expiry → second provider settlement → durable fresh-reader/GET witness. It is not yet executed and does not reconcile external invoices. | `UNRUN / not_established / not_adjudicated`; no closure |
| B67 / ordinal 193 | Does not bind a configured reuse authorizer to genuinely selected frozen evidence and a current permission owner. | `UNRUN / not_established / not_adjudicated`; retain held state |
| B68 / ordinal 194 | Calls are sequential; no N-caller single-flight, owner timeout, follower cancellation, or distinct-input concurrency proof. | `UNRUN / not_established / not_adjudicated`; retain held state |

P40 is **SAME_CLASS_DEEPER**: this widens the existing producer/ledger/consumer composition without introducing new monetary authority semantics. P37 predicates remain unestablished until the candidate is executed: local expiry telemetry and provider count are designed to be recomputed; ledger/GET equality is designed to be independently reconciled. Synthetic amounts and the repo’s environment-configurable default estimate establish no invoice, current market price, deployment permission, or production workload. The candidate’s own scope correctly excludes live-worker expiry and cross-process cache behavior.

The focused replay should retain the candidate’s exact postimage, execute the candidate against the frozen composed source, and run the removal falsifier. Keep B10, B67, and B68 open, and do not claim B66 closure or an external single-charge result from this controlled fixture.
