# R755 independent review: R748 C5b source-ref fixture repair

**Decision: GO R748 to the focused root-native wave.** The test-only delta fixes both R745 positive-path fixture defects using existing producer and reader APIs. It reloads the exact stored backtest report before producing profile-only variants, and it supplies the exact selected profiles on the positive decision-packet refs. The existing negative source/profile controls remain. This does not close B172/B173.

## Source report bytes and profile-only variants

BacktestOrchestrator.run_with_ref persists the report and then mutates only the returned Python object by setting cas_artifact_id (policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py:553–558). persist_backtest_report serializes the object it receives (policy-engine/src/polisyos/ir/analytics/backtest.py:760–787), so using that already-mutated object to produce a second manifest view changes the payload. The R745 receipt records the persisted source blob with cas_artifact_id: null and a different hash/ID from the later re-persisted return object.

R748 reloads report_ref through the existing load_backtest_report before any profile-variant persistence (virtual line 3330). The reader calls get_json_artifact and model-validates the selected stored value; it does not inject an artifact ID into cas_artifact_id (ir/analytics/backtest.py:789–791, policy-engine/src/polisyos/ir/artifacts/io.py:164–289, 292–294). The selected-profile reader verifies the manifest and payload bytes before returning the decoded source value. The existing assertions still require the candidate-B variant to retain the report content ID, change the selected manifest profile, and match the exact report bytes. This is the correct way to exercise a profile-only manifest variant without synthesizing a report payload.

## Positive decision-packet refs and controls

The second test’s positive ExperimentState now carries result.bundle_ref.manifest_profile_sha256 on the C5b ref and report_ref.manifest_profile_sha256 on the direct backtest ref (virtual lines 4207–4217). The consumer compares the complete artifact-ref identity, including selected profile (policy-engine/src/polisyos/core/artifacts/manifest.py:303–319, policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/outcome_sections.py:374–393). Both positive refs now describe the exact views returned by their producers, which removes the R745 binding mismatch without weakening the consumer.

The net patch adds five lines and removes none. Its existing same-ID/different-profile, missing/foreign/unregistered source provenance, malformed-model, duplicated-edge, legacy, and marker-retaining refusal controls are unchanged. The first test’s full source-multiset comparison, selected one-position mutation with sibling preservation, actual orchestrator report, and fresh-reader refusals are unchanged from accepted R727. Exact duplicate producer selector pairs remain unsupported and outside the claim.

The candidate remains test-fixture-only. Its report is candidate diagnostic evidence; trust and promotion remain false. It establishes no external source custody, coverage, currentness, calibration authority, or final signoff.

## Evidence and scope

- R748 packet: policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/s1-r748-c5b-real-source-ref-fixture-virtual-r2-20261013; net patch SHA 307d2f77905780a36436f96ff8d3ab642724819f3eed14042eefc2f575005e60; manifest SHA 4806b19af4d7dcfdb4a4df1e667994796516c0377d3f946d33ffb0567e114240.
- Physical base test SHA/size: afadd936b0ea50e288fd63e64f46281ad80c348dcff7066be8feb8d703426ae8, 193,910 bytes. Virtual postimage SHA/size: 25a60b8e13d242e4aa35eeac016ba7674156c4f1b75fc4e397fa513ffe3b5b97, 194,283 bytes.
- Current frame: branch codex/e02-unified-local-20261009, HEAD 9e90b725395723789c5bac428c772c199a835cea, tree e94e85fb2db3dbc4b96424698f019cf827341a14; R752 frame SHA a139743c1f9d965ab5b0cd8e284938f722c5729955d17b7b8aa10060df7ccfea.
- The patch targets only policy-engine/tests/unit/scientist/nodes/test_decision_packet_node_v3.py. The test physical preimage matches the packet. Relevant producer, reader, consumer, and governance source files match their current readback hashes and are unchanged.
- git apply --check --whitespace=error passed. The in-memory patch reconstruction matches the declared postimage bytes and SHA, and the virtual test AST-parses. Retained packet receipts show Ruff check and format check exit 0.
- No product imports, runtime tests, source/index writes, or Git mutations were performed. The focused native run remains the next verification step. closure_ids: [].

P40: SAME_CLASS_DEEPER in actual selected-source/profile binding through the real producer and fresh decision-packet consumer. The two R745 positive-path fixture defects are repaired at their existing boundaries; exact duplicate selector pairs remain a declared limitation, not another repair round.
