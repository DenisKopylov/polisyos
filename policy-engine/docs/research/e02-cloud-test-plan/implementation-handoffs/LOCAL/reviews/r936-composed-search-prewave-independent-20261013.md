# R936 — composed search, stress, Pareto, budget, and replay prewave review

**Decision: GO for the bounded Root native wave on the exact R933 composition plus R934 quality successor.** This is a source and caller qualification, not a merge decision or formal closure. `closure_ids=[]`.

## Source and composition binding

Reviewed read-only at HEAD `dae174623baca79449638758ada159ab7ebdaefb`, tree `0e7846a9576e698150de7e613d424dc72d5dd43a`, branch `codex/e02-unified-local-20261009`. The R922 frame is `root-author-source-frame-r922-20261013.json` SHA-256 `312ab0db93728b71b3e0395b8830e47dba410fe3d1a415d575ca9eb52f889f40` and records 523 physical source paths.

I walked every `final` row in R933 `raw/reviewed-search-stress-pareto-budget-replay-semantic-callers-composition-r933-20261013/composition.json` (SHA-256 `2fba15738eeaa9980b72df2106b22dbda2e1ec919b1ed1bb81967323cdd29e70`; 26 paths: 24 Python and two Markdown). All 26 current worktree files match their declared physical preimage hashes; all 26 files in the recorded overlay match the composition postimage hashes. The current Git diff against HEAD is empty for those 26 paths. R933's net patch is `6d8c4c3624266ef91b80c0ff50c674d4aab7f25529d185cc33f27a785bd392b2`; its six ordered layers include the B109/B122, B120/B123/replay, B106, B111, and R921 caller-binding patches named in the JSON receipt.

## R921 caller-binding delta

The R921 patch `4ce4aa53e2df2a282ea9128454ec2c0df6a7dd70878c86874287a87609861c26` changes only `test_rep_01.py` and `test_search_loop.py`; both final hashes match R933's composed overlay. In the resume test, `runtime_cli_main` is now explicitly bound from `tools.ops_runners.runtime_cli`, and `FileSystemCAS` is bound in the function. The test invokes the public CLI composition root with `resume`, run ID, CAS root, strict checkpoint policy, and JSON output. It does not pass `--dry-run`; it verifies the fresh checkpoint head advances to the remaining `finish` node and records both completed nodes. The source route parses the command in `runtime_cli.main`, dispatches through `_dispatch_core("._cli_replay", "_cmd_resume", args)`, builds the requested filesystem CAS, and calls `resume_from_checkpoint`.

The autotune producer test now locally binds `FileSystemCAS` where it constructs the real store. It drives `SearchLoopRunner` through `TracedLLMClient` and the Gateway client with a durable `BudgetMiddleware`/`FileBudgetLedger` and typed producer run binding. The finite-cost case resolves the exact settlement and runs Stage B; the boolean-cost case remains unknown and runs no evaluation. These are actual consumer paths with a fake HTTP transport, not mocked budget-read results. Neither test was executed in this review.

The composed replay positive remains an ordinary `runtime_cli.main` call: it requests a Foundry replay, then checks the persisted `foundry.simulation_result` manifest. R921 fixes the separate resume caller binding without replacing the Core handler or bypassing the CLI parser.

## R934 formatting and import successor

R934 is bound to the exact R933 composition SHA. Its manifest `5097e2717237bda5c8d83c31b63f386f7003ccfcd37053007b04da3ee4eef995` covers 24 Python paths and ten changed postimages. For every row, the before hash equals the R933 overlay hash and the after hash equals the R934 overlay hash. The patch is `c38e7403f0b536d4673f4f1d901c5762140e69d67efaaf007363b0bf8ed07678`.

The recorded product-configured Ruff check and format receipts are exit 0 for all 24 files (48 commands total). I did not execute Ruff. Independently, standard-library AST comparison with import nodes removed, scoped import-binding multiset comparison, and comment-token comparison all match across all 24 pre/post pairs. The quality successor therefore resolves the earlier R833 formatter-only stop without changing these composed semantics.

## Composed semantic boundary

The unchanged R833/R858, R891, R907, and R916 reviews remain the controlling scoped reviews for the earlier mechanisms; their exact SHA-256 references are in the JSON. This composition preserves the finite-history plateau gate and typed Pareto assessment/reader behavior; B111's selected source-occurrence survivor assertion remains intact. B106 evidence is produced from persisted finite occurrence rows and recomputed by the fresh Level 5 and Blueprint gate consumers. A continuous-severity source stays `profile_mismatch`/`mixed_unscored` with no promoted score; missing, legacy-unknown, malformed, stale, and wrong-candidate evidence remains limited or refused. `warning` plus `defer_to_human` is still an unaccepted external calibration/G choice.

B120 remains limited to the exact candidate-generation adapter and durable settlement owner. The provider spend is consumed by the controller's cost stopping path; ownerless generic Stage A/B evaluator calls and pre-dispatch maximum-price reservation are outside this mechanism. External invoice truth is not established. B123 reaches typed objective evaluation, best/frontier, persisted Pareto state, fresh registry read, and candidate transfer, but still lacks a protected publication consumer. These are bounded, explicitly preserved limitations; candidate transfer is not publication acceptance.

## P40, native selectors, and limits

P40 bucket: **SAME_CLASS_DEEPER**. This review composes already reviewed mechanisms and verifies the R921 caller-binding correction and R934 quality layer. No new class was found and no further instance patch is recommended. Keep the B120 and B123 residuals explicit and test them with the ownerless evaluator and missing protected-publication falsifiers; do not turn the unratified B106 proposal into accepted authority.

Root's focused native selectors are the ten test modules listed below and in the JSON: `test_search_loop.py`, `test_phase_b_policy_runtime.py`, `test_pareto_transfer.py`, `test_adversarial.py`, `test_phase_d4_runtime_integration.py`, `test_stress_scenarios.py`, `test_pareto.py`, `test_phase_d4_challenge_suites.py`, `test_cli_replay.py`, and `test_rep_01.py`. The JSON also names the exact critical nodes, including both R921-fixed callers. Native tests, product imports, Ruff execution, and database work remain **UNRUN** here; Root owns that wave after source freeze.
