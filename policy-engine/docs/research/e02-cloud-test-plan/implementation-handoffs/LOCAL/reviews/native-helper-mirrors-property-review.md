# Native Scientist helper-mirror property review

## Scope and evidence boundary

This is a read-only semantic review of the 23 test paths in `LOCAL/raw/native-helper-mirrors/first-combined/command.json`, grouped as welfare 8, distributional 5, blueprint 4, support 2, governance 2, and transport 2. The measured checkout was branch `codex/e02-unified-local-20261009`, `HEAD=4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`, tree `741784521d909f775d50863a29deec63cde300cd`; the working tree was dirty (40 tracked modified paths plus untracked paths). This is a candidate-WIP source-bound review, not the final source/input/backend freeze, not a final composed replay, and not a finding closure.

The only combined run reviewed was the retained first run: 23 paths, 51 collected cases, 38 pass / 13 fail, exit 1, 10.890 s. Its exact command and output are in `LOCAL/raw/native-helper-mirrors/first-combined/command.json`, `stdout.txt@sha256:08bbea3f3a4a488d12b2ebe050e3711f65cbc1091a24fadd12ff44908000aa2c`, and `junit.xml@sha256:e87a540bf36f52af1fb514b7ed7ae46b8096e459566172d347f4fbda2fc2abbd`. `command.json` marks `source_freeze:false`. Nine test files have since changed from the first-run input manifest: welfare context, welfare propagation, welfare reports, blueprint engine, blueprint strategy, blueprint reporting, runtime artifacts, normative arbitration calculations, and transport results. Thus the first-run failures are historical evidence for that earlier WIP only. No test was run for this review; current passing status is `UNRUN`.

The review applies the repo's P29/P32/P37/P38/P40 rules. It treats test fixtures as synthetic candidates, not law, issuer evidence, causal ground truth, or promotion authority. No author-proposed closure is upgraded to a formal closure here.

## Semantic disposition

Most mirrors are real helper-level behavior tests: they exercise signed interval arithmetic, typed uncertainty, retry accounting, persisted CAS artifacts and readback, distributional calculations, alignment, benchmark scoping, result refusal, and mixed normative statuses. None of the 23 files is a pytest re-export wrapper. Some coverage overlaps with existing node-level tests—especially welfare retries and partial reports, ordinal poverty, aligned subgroups, and MTR bounds—but those are complementary helper tests, not duplicate imports masquerading as tests. The legacy route witnesses include `tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py` and `test_run_distributional_analysis.py`.

Four material boundary gaps remain in the current WIP:

1. **P40 bucket: same P38 class, deeper — explicit invalid input collapses to absence/default/another value.** In `welfare_context.py`, `_resolve_pe_sensitivity()` returns identity defaults when the field is present but is the wrong type, empty, or yields no valid coefficient (`resolved or defaults`). The current mirror tests one valid coefficient plus one invalid entry and the wholly absent case, but never an all-invalid explicit field. `_resolve_base_response()` likewise ignores a present non-mapping/non-sequence `pe_response` and may proceed to metric/order defaults; the test covers a valid response and a missing requested metric, not malformed-present input. In transport input resolution, `_resolve_treatment_value({"value":"invalid", "dose":3})` is explicitly expected to return `3.0`, and an unsupported explicit `transport_solver_mode="fastest"` is explicitly expected to become `"auto"`. The PAG test accepts `501 -> 500` and `1.5 -> 1.0` without checking a surfaced normalization/limitation; unknown `pag_identification_policy` is not tested and the helper returns arbitrary nonempty strings. In governance request construction, malformed `gate_iteration` is explicitly normalized to 1, timeout 0 to absent/no timeout, and a non-string profile to absent. These are the same semantic class across several fields, not separate instance patches: preserve the distinction `absent | valid | explicitly invalid`, then refuse, limit, or surface a declared normalization. The falsifier is the same malformed explicit value with a valid lower-priority/default source available; it must not silently produce the same result as omission.

   A second P38 boundary is in welfare method selection: the test asserts that `_resolve_requested_welfare_method()` preserves `"future-method"`, but the consumer dispatch treats every value not in interval/robust/deterministic or delta as Monte Carlo. The helper-only assertion therefore passes while the consumer interprets the unknown method as MC. Add a consumer-path test requiring typed refusal/limitation or a separately declared fallback; a preserved string alone is not the property.

2. **P40 bucket: same P38 class, deeper — key/shape checks stand in for replay/source validity.** `_gate_replay_readiness()` counts keys, not resolved refs or their kind/content. The new “complete” case supplies arbitrary `test.<key>` kinds for `input_bindings_ref`, `norm_pack_ref`, `knowledge_bundle_ref`, and `research_intent_ref`, yet asserts replay completeness. The current code would also count dangling or cross-kind refs as complete. `test_malformed_human_review_request_is_replaced_and_persisted_pair_is_reused` tests replacement of an invalid dictionary/invalid ID, but does not test a parseable request paired with a dangling, wrong-kind, or content-mismatched ref. `_ensure_human_review_gate_request()` returns early for any parseable request plus parseable ref without resolving the artifact or binding the payload to the request. Distinguish caller-supplied malformed input from a known generated cache, and prove the latter by CAS readback/content/identity binding. Otherwise a shape-valid proxy controls a gate context whose request ID, phase, run, and evidence may diverge.

3. **P40 bucket: same P38 target-selection class, deeper — graph membership is not target intent.** `transport_resolution_results._pick_legal_target_variable()` chooses `new_node_name` if it is a graph node, otherwise picks the first affected-edge destination in the graph, then its source, irrespective of `mapping_type`. The mirror test constructs `MECHANISM_NODE` with default `new_node_name="unregistered_legal_node"`, accepts target `income`, then accepts target `policy` when the declared edge destination is missing. Its comment declares source-endpoint fallback valid, but the test does not distinguish a mapping that explicitly intends an edge endpoint from a stale/contradictory named mechanism target. Add separate positive and negative cases for mapping-type/target semantics; require a typed unresolved/review outcome for an invalid explicit target unless the mapping contract explicitly authorizes endpoint fallback. The hard-coded `UA:policy-register` and assertive legal description are invented fixture data; label the fixture as synthetic and explicitly non-issuer/non-law evidence.

4. **P40 bucket: new class — caller-asserted completion flag is not an observed-completeness witness.** `test_partial_report_keeps_conditional_summary_and_selected_input_lineage` calls `_persist_welfare_mc_report(..., complete_draws=True)` with a draw set whose `requested_draw_count` is 3 and which has only two successful/terminal rows; a separate provenance dict instead claims requested 2/failed 0. The helper trusts `complete_draws` to choose `draw_summary`, so this positive call does not prove a complete report. Use a consistent full draw set for the positive case, an incomplete set for the negative case, and preferably a real producer-to-fresh-CAS-consumer witness. If completeness remains caller-derived, the test must exercise the deriving caller and mutate the outcome rows while retaining any caller flag to falsify that premise.

Other qualifications for interpretation:

- Distributional justification correctly keeps marginal identification separate from scenario-only coupling and emits a negative certificate. Its `policy_shock -> income` graph is hand-built and test-scoped; passing this test proves behavior conditional on that graph, not that a real graph's edges are independently grounded.
- The blueprint calibration test uses `state.params["correlation_metrics"]` with `sample_count=8` and no source artifact/tracker observations, then observes the helper's projection. The test itself asserts `promotion_ban_active=False`; it must not be presented as independent calibration evidence or evidence-based promotion.
- `test_policy_runtime_artifacts.py` directly persists a fabricated `FunnelExecutedWorkPacket` whose `backend_kind` is `"production"`; it verifies serialization, CAS lineage, selected view, and tamper detection, not that a production backend actually ran. Use a test/synthetic backend label or make the non-promotable fixture boundary explicit so the test cannot be cited as production-producer evidence.
- `test_policy_blueprint_runtime_benchmarks.py` usefully tests per-source status precedence (existing report path vs missing suite path) and exact loop/split/scope filters. File `AVAILABLE` is path availability, not proof that the report payload is valid benchmark evidence.
- `test_distributional_analysis_ordinal.py` supplies its simulation-result ref via `artifact_ref_factory`; its helper proof is report construction and lineage declaration, not successful loading of that simulation result. The existing node-level test covers the composed route.

## First actionable test queue

1. Add one table-driven malformed-vs-absent contract at the consumers for welfare sensitivity/response and transport query, treatment, solver, PAG policy, seed, and bound settings. Cover missing, null, wrong-type, invalid numeric, nonfinite numeric, unsupported enum, and valid lower-priority values; assert the invalid signal remains limited/refused instead of becoming a default. For the unknown welfare method, call dispatch and inspect the actual method used.
2. Strengthen governance replay tests with missing, dangling, wrong-kind, wrong-schema, and cross-run refs for every required replay component; “complete” must depend on the typed refs the replay consumer can actually resolve. For the human-review request pair, mutate request ID/run/phase and ref payload separately, and show that malformed external state is not accepted as a generated persisted cache.
3. Split transport legal projection into a well-formed named mechanism node, an intentionally endpoint-targeted modifier, an unknown named mechanism node with valid edge endpoints, and a missing-edge endpoint. Assert the contract's exact target or unresolved status. Replace fixture issuer/legal prose with explicitly synthetic source IDs.
4. Make partial/complete welfare report fixtures count-consistent, then retain a negative that changes only terminal outcomes/counters while keeping the declared completion flag. Assert no unconditional `draw_summary` survives.
5. Keep the current good mixed-status, CAS roundtrip, and source-scope tests. Where existing whole-node tests already cover the same concept, cite those routes as complementary integration evidence rather than claiming a second independent capability.

## Exact path and current working-byte hashes

These are the 23 current test-file bytes measured during review. They are WIP hashes, not hashes from the retained first run unless equal to the manifest.

| Group | Test path | Current SHA-256 |
|---|---|---|
| Welfare | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_welfare_types.py` | `d10abd834bedb9c9016a054294690e1c012726cc579054963cc0744eb7f2a1c3` |
| Welfare | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_welfare_context.py` | `20c4a72527f88f759c083060af52746b541e1a332389233e3b39bd1f73636f9e` |
| Welfare | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_welfare_ge.py` | `e08d43f4f381a1938a166150ee8c046992fd54d7db5ac67bd72c321f812200e1` |
| Welfare | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_welfare_covariance.py` | `210a0c950507071736f79e06249af92f72d7329954c3963390da15c6d139dcec` |
| Welfare | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_welfare_draws.py` | `699f06a6085796983e070ebe6ab6de8f572e09e326dac764908e2612c4bde042` |
| Welfare | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_welfare_propagation.py` | `58d14438e0081d64772d33fcfc2b05633cb3dcc89ac1afcd4f124a78f3fb20cf` |
| Welfare | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_welfare_reports.py` | `eb9dce7323065d1b28d7d3c248d4d7bfc72a1dbd9f670562906352784ac1d27b` |
| Welfare | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_welfare_node.py` | `ed9ca3f6473b7b45bf6faa9fb77d2277765a9ab82b3b07ad1d49ca3be3324b8b` |
| Distributional | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_distributional_analysis_ordinal.py` | `7803e1af6edb923da5b21d0b52e75639ba75723a1b29c712f1f90c7a06517702` |
| Distributional | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_distributional_analysis_justification.py` | `3e7485ea9ed839c30adf0cb0135e3d07ab5f154c4a2da81564973370add242fc` |
| Distributional | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_distributional_analysis_bounds.py` | `4ed543a52d050b023889e2d2bbb6e889ef6501ee67d4a6b1aeb843e9225804f0` |
| Distributional | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_distributional_analysis_artifacts.py` | `0742785ed8e402a02cd107bc6ec9751cd891729b8e813f2d6714316fd1e1ba6f` |
| Distributional | `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_distributional_analysis_subgroups.py` | `0c9fcd8b8c9650d2b7e406cb6befca49a2439a04af67758150c4b3b04c553026` |
| Blueprint | `policy-engine/tests/unit/scientist/nodes/builtins/decide/test_policy_blueprint_runtime_engine.py` | `8e9a3d03975ec8c47c0fc445525f312b7b8f30607a95e84c09169a5eee874126` |
| Blueprint | `policy-engine/tests/unit/scientist/nodes/builtins/decide/test_policy_blueprint_runtime_strategy.py` | `6a3bdfc8031ee796a96f9eb152077ae6e4a85d8975242fdafab4bfc36690b42f` |
| Blueprint | `policy-engine/tests/unit/scientist/nodes/builtins/decide/test_policy_blueprint_runtime_benchmarks.py` | `1c554bcad1151897b817aec02503e40a8d8879811dfb2b1d619662e9213e3ec4` |
| Blueprint | `policy-engine/tests/unit/scientist/nodes/builtins/decide/test_policy_blueprint_runtime_reporting.py` | `74c974a3e2222b448b3abaaa11370df24b19c0a8d5832742862531664a4afaef` |
| Support | `policy-engine/tests/unit/scientist/nodes/builtins/decide/test_policy_runtime_artifacts.py` | `e0694e5d7a4696aca69f2608274c8cad224a627afbe68dbbbf4784365175d2d5` |
| Support | `policy-engine/tests/unit/scientist/nodes/builtins/decide/test_policy_runtime_metrics.py` | `6e284595aa647a5e3209ac844615d47180b1960264d74c71ee8c8675779e7c01` |
| Governance | `policy-engine/tests/unit/scientist/nodes/builtins/governance/test_normative_arbitration_calculations.py` | `149ee19399c48411a6d7638402f601962758854093d16bf80605bf61530e2a63` |
| Governance | `policy-engine/tests/unit/scientist/nodes/builtins/governance/test_governance_gate_requests.py` | `56ab259948b9d034de94460d55a3626a68b6b289e9972f8fc458573c53b63df8` |
| Transport | `policy-engine/tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_inputs.py` | `c03542af227f1e32f637b1f474958dd126774a319f584f38d1d0e4ee66347e03` |
| Transport | `policy-engine/tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_results.py` | `7e2369bba61632a61ded52de6d5b815e5dae8cff97fcdcee2059cfa653cb70af` |

The current directly imported Scientist helper/source modules below were also SHA-256 read during this review. They are not an assertion that every transitive dependency or the full tree is frozen.

| Source module | Current SHA-256 |
|---|---|
| `policy-engine/src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py` | `4696f3c37f1edb287527776d1579fd98ae0d94b8d4d513c9571328bf1e0d51cc` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/causal/transport_resolution_inputs.py` | `0d9601de272f6067b2384111fb09d783d8cbfffa46500ed2bd0dba21ee717703` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/causal/transport_resolution_results.py` | `c607b069be5fcd8d537e7ce53a92e3321ccaa1904007581a40276a81b8074cfa` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/__init__.py` | `bf81f636371a10e0e8a6f26640b41b0a1459130ce017c0029dc11b43a8106dde` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_benchmarks.py` | `202fd486a09a610fcd681af45c2b24f43a511d9bdf5767e7256aa53899508ff2` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_engine.py` | `15f508608cbb931226d24efb111c2e325ed1a83d4cef1ae6cf492f74beea66ff` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_reporting.py` | `68877a5dc66ddbf8a59644eb72377ea34091243dbdd708da64aff6298848c883` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_strategy.py` | `cd11f2fd0542c14821aee9ad41224f79618d04a3aef559d039c283647f6fc1c6` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_metrics.py` | `0de6efcb9de46c2938b0bbe7d6e87274236c903285ff180440ea64b3e74bf164` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py` | `c97671fbd57c8b410fb8a352b294db62265bf3fd513abf93abc8c5c5ffe4a992` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/governance/governance_gate_requests.py` | `14fab09e4e63427db8a6a06032d44f00952fa32eda5e13200d2a1c9ce852fbc7` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/governance/normative_arbitration_calculations.py` | `d168ec331b803fc2ce01bc089e1ece4adfb9b9647c459accb3a6480fb021b623` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_artifacts.py` | `20eba50c64248977e4e110e7faf6032544afadc4790db6ef8be062b7d8d1e4d7` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_bounds.py` | `e19bab487de4bc1f1b2e10369997dc8498c1b7af9197c2634de584386d420c6d` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_justification.py` | `449970c269d7457fd13ef7ab85b9b32bf18848fecd5dfa871bec1a3ec4caa11d` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_ordinal.py` | `89ca3fcd8368736e54f00ded2a1b454ad1bd5d0d34a913c86358a1c7502365c1` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_subgroups.py` | `fbb9b5423b3e3e38a195678e218de8d1dbb33d3ab59404429c504b03b44147c0` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py` | `993a434317e54b6db23626ba56e60e0973312fe960e57cc2c2cc76cdae981c7f` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/welfare_context.py` | `67b8d609fe101e9b13756b651af03bb0740940e7415a6913b3f30c11581b116a` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/welfare_covariance.py` | `c5cb907b8312b52f0504cbacf3e2a38e147909a0acf8db6d04ac741607bc2d65` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/welfare_draws.py` | `99d2adc8509354890a92de6380e23b973966f141f5a2b7a68f3fa2e8f2f09d38` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/welfare_ge.py` | `ad740b6579a91b76ff005b3c2bbecd7a1f84d4827298627ec08f5aae84f41cea` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/welfare_propagation.py` | `3633130f341dea915e1876ca1e148c7e26cd0ab34811d4fed870c240686a24bb` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/welfare_reports.py` | `5040ee6a1192a88551ff6efc83944cb8b5e2f44fe508e9368a85ed11ac8d3807` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/welfare_types.py` | `80c7724be00d61bb2202d322b70d0bc2d525ce7d23328e9bf1bc0557af1a00a8` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/state_keys.py` | `d2cf26377a0ba6e2f5ae9164512391c1c619e2a97f72bb1dd5f7723094dfcd0d` |
