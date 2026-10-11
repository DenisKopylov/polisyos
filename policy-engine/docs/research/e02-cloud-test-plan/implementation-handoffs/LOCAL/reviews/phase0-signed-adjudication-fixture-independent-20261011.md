# Phase 0 signed adjudication fixture — independent review

## Verdict

**GO to apply and run the one-test patch.** It closes the current Phase 0 test gap by carrying a typed, persisted, verifier-approved adjudication through the existing graph loader. The patch is a test-only witness, not a product-code change or a claim that the synthetic evaluator is a deployed authority. The focused test still needs to run on the applied bytes before reporting a runtime pass.

## Bound inputs

Candidate checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`; product root: `policy-engine/`. Current review HEAD: `347e61b84694986bf7fdc5adea0054326c05a213`. The integration test is unchanged at SHA-256 `83831d5821cd0a8003a7547e14987cf0eb847f0a8a0f27ce48cb40e05c6f5b2c`; the patch target matches that preimage. The assigned frozen patch is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/batched-blocking-focused-20261010/data-forge-five-real-producer-consumers-20261011/phase0-signed-adjudication-fixture.patch`, SHA-256 `c134d9cd45b98483e611655702f5ef2e1766a34ea59cdc3f05474e0f00a85228`. A read-only `git apply --check` from the worktree root returned exit 0.

The relevant existing bytes read during this review:

| Path | SHA-256 |
|---|---|
| `tests/integration/test_phase0_quality_validation.py` | `83831d5821cd0a8003a7547e14987cf0eb847f0a8a0f27ce48cb40e05c6f5b2c` |
| `tests/unit/data_forge/domains/academic/batch/_claim_evidence.py` | `c47e043da152e9ee9f45d697c2560419da0b9ea9c88a1f477bbfeec59c5c6a0b` |
| `tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py` | `b58648d6ba988eae7d35c3288bf74cc41db41f43c6c7fe705fc5adce3b7dfebf` |
| `src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py` | `735848c2a900d7b035ddbebfff06ce5fefd2954c4f3f09ad5c131ee13475d207` |
| `src/polisyos/data_forge/domains/academic/batch/claim_adjudication_verifier.py` | `1641aa6eca22d0796fc879ad034104b266305c87640835d4be9c7faa292d419f` |
| `src/polisyos/data_forge/domains/academic/batch/claim_adjudication_policy.py` | `b8eb3a3c57d95e198990103bc01bf2b33f9b4129f1a2c447b0864498c928f1bc` |
| `src/polisyos/data_forge/domains/academic/batch/admitted_claim_adjudications.py` | `32e1dc79651082078886303ce34afac29cb8d5085d85cead69a81609bbc1cb66` |
| `src/polisyos/data_forge/domains/academic/batch/graph_builder.py` | `0d1b79b2dc45d3d97dbb7f2414be69ecae534a1212dfdaa917b21b9a272b996d` |

## What the patch exercises

The patch keeps the existing candidate-only load first and asserts `raw_claims == 200` while `claims == 0`. It then calls the actual `produce_claim_adjudication_input` against the integration flow's persisted extraction output, builds and stores a signed fixture over those actual input item IDs, persists the typed batch and lineage, and invokes `materialize_claim_adjudication_result(..., verifier=...)`. That consumer calls `load_admitted_claim_adjudication_batch`, validates the result manifest/lineage and exact input denominator, and invokes the concrete `ClaimAdjudicationVerifier.verify_batch`. The final `run_graph_load(..., verifier=...)` goes through `load_verified_claim_adjudication_rows` before admitting data to the DuckDB graph. The patch checks 200 raw and 200 admitted claims after this second read, plus the persisted Phase 0 report.

This is a behavioral route, not a marker assertion: persisted inputs, result, verifier replay, graph ingestion, SQL readback, and report result are all on the path. Re-running graph load is safe for this test: `load_graph` resets/recreates the graph tables before loading, so the initial candidate-only pass is not accumulated as duplicate rows.

The existing verifier suite supplies independent refusal controls. `test_self_issued_or_incoherent_evidence_is_refused_at_both_intakes` covers invalid signatures, an unappointed signer, missing observations, champion tampering, and metric inconsistency at both Scientist and Data Forge intake. `test_empty_deployment_appointment_cannot_publish` checks missing appointments. `test_valid_champion_does_not_authorize_fabricated_run_result` checks replay mismatch. The graph tests reject raw/unminted rows and recheck the current champion at graph use. These are unchanged tests and were read, not executed in this review.

## Captured prior red

The supplied captured run uses HEAD `785944776c39722923c3a34d4ab7a3594dc03287` and the same integration-test preimage. Its graph manifest records `raw_claims: 200`, `claims: 0`, `claim_adjudications: 0`, and `source_provenance.authority: candidate_only`. The test then fails at the final Phase 0 report assertion because the required report does not pass. The captured JUnit records 22 passed and one failure; the captured stdout reports 11.09 seconds.

| Evidence | SHA-256 |
|---|---|
| `.../data-forge-five-real-producer-consumers-20261011/command.json` | `5ba0da2fd66446ef7e8d572aef6388423d04a782ae813a2b178d5a02c18e6e5f` |
| `.../data-forge-five-real-producer-consumers-20261011/stdout.txt` | `0e658f68e7b3604678392131a079417cee6688684101de61a8ab4b25789663ae` |
| `.../data-forge-five-real-producer-consumers-20261011/junit.xml` | `e47736d5a45f4719e0f5c97820f76c1b58d2d8505d4e6ed3f67c8600de800e8c` |
| `.../fixtures/test_phase0_quality_validation0/snap/academic/manifests/graph_load.json` | `829a8f6f38a4a4c1d0313a70ddaef457e897216af15fcee740d3d3f1369f0d2c` |

This is evidence for the candidate-only baseline and the reason for the test delta. It does not prove that the proposed patch passes.

## Scope and limits

The helper's private Ed25519 key and appointment are intentionally test-generated. They exercise real signature verification and a verifier-supplied appointment, but do not establish an independently deployed evaluator appointment, a live Scientist model run, external evidence quality, production freshness, or real-world claim truth. The deterministic extraction provider and connectors remain synthetic. The expected positive outcome therefore establishes only this fixture's existing admission and persistence path.

P40 classification: **SAME_CLASS_DEEPER**. The existing unit suite already exercises the verifier contract and refusal cases; the missing layer was a Phase 0 producer-to-persisted-result-to-graph consumer witness. The patch widens coverage at that real consumer path instead of weakening the candidate-only gate. Relevant patterns: P01/P02 (bridge completeness), P05 (authority), P29/P32 (behavior over markers/form). This review ran no tests, imports, lint, or scientific evaluation and makes no closure or G-adjudication claim.
