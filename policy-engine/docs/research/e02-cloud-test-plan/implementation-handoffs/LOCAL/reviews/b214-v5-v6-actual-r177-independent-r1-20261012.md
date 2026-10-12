# B214 V5+V6 actual R177 independent receipt review

**Verdict: GO-limited for the applied graph-admission property and V6 test-oracle correction. The whole B214 semantics decision remains open; `closure_ids: []`.** The physical worktree readback matches the frozen V5+V6 composition. The retained final CPU run has 547 passing selected-consumer tests. This is not a formal B214 closure or a claim about PAG/CPDAG completion truth.

This review is read-only with respect to product source, Git index, and history. It writes only this new review pair.

## Identity and applied readback

- V5 patch `raw/b214-admitted-consumed-snapshot-author-v5-20261012/candidate-v5-delta.patch@766256aa46e5b90f0e99d3741dca288cf4f05bf0f297c5279a4e7f7addfc906f`; manifest `candidate-v5-manifest.json@db21b9d12e0fc298a1be176beb4b6d9b485a5552aa0df66ffca803db92225e0e`.
- V6 test-only delta `raw/b214-admitted-consumed-snapshot-author-v6-20261012/candidate-v6-delta.patch@96ad8c040b7b261c7c67968be79846920763beb2df4aad30bab23aef3d3898e6`; manifest `candidate-v6-manifest.json@d397d5e5fc47c879cd434dbc5fa45819281ed434f59aa688695fb494f2c122a8`.
- V6 changes only the serialized-alias oracle in `test_symbolic_identify_y0.py`: it replaces an unsupported fixture-specific `IDENTIFIED` expectation with exact full-output equality for typed, JSON, Python, and revalidated profiles. It does not change runtime source or scientific semantics.
- Root composition receipt `raw/b214-v5-v6-root-composition-r168-20261012/composition.json@87d06ef797b57fdca8d96ddc49642840dddd3c04e308f9549cc8866b3313454f`; composed patch `net.patch@8f9c2a4d47d516335847a791452901d5efbe9a23f31b16b6646dd2a4014e33f6`; separate physical readback `application-readback.json@60962c9ac4633986c15df88e92120581bc8b12ad1fa5a1542b4a635dea6b4844` records all six composed postimages matching and `diff_check_exit: 0`.
- Actual worktree: branch `codex/e02-unified-local-20261009`, HEAD `e635319f150c55b529357888b582ec857220c3a6`, tree `6e09d0ca6158920805f76374bdfa076cb7ee73c4`. The index was empty. The candidate base was bound by target preimage hashes; the root composition was applied over this actual HEAD.

The seven product/test/documentation paths in the B214 consumer footprint are below. Hashes are the values read from the physical worktree and match the V5/V6 packet. The two registered route modules are manifest-bound unchanged companions, even though they are dirty relative to the branch HEAD from the surrounding shared worktree state.

| Path | Candidate relationship | Actual SHA-256 |
| --- | --- | --- |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_engine.py` | V5 runtime change | `b4175a682aaa72959fa4e2675d8997d2159b74be9a768483201593fc51268129` |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_check.py` | unchanged registered consumer companion | `7e31b3f2c97ae1a72f1a7663f2831ccb7d99defdf6a5912dc94ce92d70d70218` |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/symbolic_identify.py` | unchanged registered consumer companion | `01c8870f44b4013318e28ab17c0b8fe6230ceccbed03ee88e2eda2b16d13beb1` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_transport_check.py` | V5 regression tests | `3b3f5cdb435329b15dee1f2ff3dae31f19c263f57ae455e0a049305fcc0924fc` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_symbolic_identify_y0.py` | V5 tests plus the V6 alias-oracle hunk | `13666857c1cc6347744520dfcaa28e6ba26b41111848b92a71fc25b07db76269` |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/README.md` | B214 text composed over the shared dirty preimage | `e43ba97f9b6341cc9732663401d4b521bb00883a27c037d9f30e38cbae2860bd` |
| `policy-engine/release-fragments/unreleased/2026-10-11-e02-b214-pag-refusal.toml` | V5 release fragment | `28c0e358fd37096658f2dfa3da8800a246f5cc825282974e10256cc6d9105b88` |

The composed six changed paths also include the author proposal `LOCAL/b214-fullgraph-admission-v5-20261012.md@53b07c3ec7afdc42de7a37beeb4b7bc5ec44477423bf696f97724816d7b40eee`; that proposal is outside the seven runtime/test/component-documentation paths above. The README postimage matches the composition and retains the shared tail already present in the V5 preimage: B214 admission text is at lines 25–42, while the native causal value/N8 run-basis v2 notes remain at lines 301–327.

## Actual selected-consumer run

The full exact argv, cwd, environment and before/after inventory are in `raw/b214-v5-v6-actual-selected-consumers-r177-20261012/command.json@2bace3270410f7963261dd4007dd778f66cd7d26a7da59137803095db00cb2a2`. It ran from `policy-engine/` at the actual HEAD above, with `PYTHONPATH=tools:src:.`, `JAX_PLATFORMS=cpu`, and the two affected causal unit modules. Retained complete outputs:

- stdout `stdout.txt@85689d0b816d48d14ce7d2686e8f90ff307ed3ead86fbea2017d1753f09bc676`;
- empty stderr `stderr.txt@e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- JUnit `junit.xml@0ecb4e2ef657ee0bb967ff8024ff2319cffb7fca175a2f294d5a2d6d1c78a122`.

The JUnit root reports **547 tests, 0 failures, 0 errors, 0 skipped**, 4.201 seconds pytest time. The command record reports exit 0 and 7.49369075 seconds wall time. This was the root’s final selected CPU consumer run; I did not rerun pytest or invoke a JAX/Metal or full-backend wave.

The actual run contains passing witnesses for the complete selected surface: hidden-S-node refusal across four registered methods plus the direct solver; eight noncanonical-container route cases; same-snapshot consumption across four registered routes; post-admission graph mutation in registered check and direct solver; four public `MethodDispatcher`/`NumpyRunner` refusal cases; and the corrected serialized-alias equality test. Resolved positive controls remain separate from refusal cases.

## Behavioral removal evidence

The final JUnit passes the older gate-removal controls `test_symbolic_partial_graph_refusal_gate_removal_control` and `test_symbolic_admg_profile_gate_removal_restores_frontdoor_claim`, plus all four `test_remove_endpoint_profile_predicate_keeps_markers_but_restores_identification` route variants. The test source removes the partial-graph or endpoint/profile predicate while retaining the generic typed refusal/proof path; the actual front-door route then returns `IDENTIFIED`, and the refusal assertion is expected to fail. This is a property-removal control, not a marker check.

The independent V5 snapshot-removal probe is `raw/b214-v5-independent-oracle-r1-20261012/removal-r3.stdout.txt@82037ab2f025560f9ee5c70dc8da5034bf2273274e4258ea60645ec03367e621`. It replaces `_snapshot_typed_model` with identity and runs the hidden `model_copy(s_nodes=HiddenSNodes(...))` case on Check, SymbolicIdentify Y0, SymbolicIdentifyV2 fallback Y0, and SymbolicIdentifyV2 native. All four assertions fail because the routes again produce `IDENTIFIED`. This mutant’s selected test body is exactly the applied V6 body (function-body SHA `9ccf4e78f5b770b1bf395dfb06e2e00dbc4a2fe6a6d4c409fa0f4693e5310ede`); V6 changes a different alias-test hunk only. The engine hash is identical across V5 and the physical postimage. That is direct evidence the snapshot behavior—not only refusal markers—is load-bearing.

Retained source-bound independent V5 evidence remains applicable because V6 changes no runtime and only corrects the alias oracle: 20 focused cases `focused-r3.stdout.txt@c193760d56e93b51ae11f89e8f8519620f6a26c408c1167f665bba9b9dc3b30d`, 360 complete graph-type/ordered-endpoint/storage-order/registered-route matrix cases `matrix-r3.stdout.txt@3b84a2adeb79d2c67356c96e3684ab361328b440b87bdd38efcec980557fdff3`, and 30 nested-schema adversarial cases `adversarial-r2.stdout.txt@091914735ac7f545fa198ccf7542a2b45eeb417b644386597b658a6586a4b8d5`. These were retained, not rerun for this actual-receipt review. Their source-bound disposition is in `reviews/b214-v5-admitted-consumed-snapshot-independent-oracle-r1-20261012.md@bd2d668ea76a758bedfe11ecd0231a6c4bb6c0815bc51256c50f4b4422289a58`; V6 review is `reviews/b214-v6-test-oracle-independent-review-r1-20261012.md@498d50776e47c726876c53d621f53ff922be50a19ef1470cbb0637f5be61b036`.

## Property, premise labels, and limits

**P40:** `SAME_CLASS_DEEPER`. V5 widens admission to the complete detached `SelectionDiagram` that the gate and consumer use, across registered routes and the direct solver. V6 corrects a test oracle only. The complete-profile quantity is exercised by the generic schema snapshot/rebuild and the current route tests; there is no new one-leaf repair claim.

**P37:** the admitted diagram field set and nested consumed values are `recomputed` from declared runtime fields and annotations; canonical resolved DAG/ADMG structure is `recomputed` and delegated to the existing static ADMG validator and topological-order owner; exclusion of metadata from that static graph profile is `independently_reconciled` against what that owner consumes. PAG/CPDAG completion semantics, extension-set coverage, probability, external causal truth and publication authority remain `not_established`.

The implementation’s observable result is a typed limitation/refusal for unresolved or unsupported scalar graph profiles before method-local formula/proof emission, while retaining resolved static DAG/ADMG paths. This does not decide whether partial-graph output should be selected-extension conditional, invariant over every extension, set-valued/bounded, or probabilistic. The original G decision remains unchanged at `integration/decisions/B214-pag-extension-claim-options-2026-10-11.md@bcce607e2bfe1c1a333b6ede146e2cac8324fb959ca006fd4360f7496c97af8d`; its four alternatives remain open. No graph truth or external theorem is established by the structural gate.

The earlier V5 broad attempt remains preserved as failed (545 passed, 2 failed). V6 corrects the candidate-owned alias expected-value defect; the separate JAX/Metal failure remains `not_established` under the prior P41 record. This review does not rewrite that history or treat the previous attempt as green. The final root R177 selected CPU run above is a separate post-composition receipt.

**Formal result:** candidate property GO-limited; whole B214 completion/semantic acceptance held open; `closure_ids: []`.
