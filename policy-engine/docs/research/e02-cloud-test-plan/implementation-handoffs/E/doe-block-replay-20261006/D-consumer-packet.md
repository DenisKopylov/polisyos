# DoE → default Search: owner-ready consumer packet

Implementation: `f07b7d485531b96a206ae9b2aad7acf5f2755324`, tree
`8dcd5c26a4868e1b055a54a6cd53365e9d5890f3`, base
`028829629a9c30454e44d25e7bea7be3ea05b561`. This extends the existing
producer/reader; it does not introduce another search runtime or close B100.

Canonical next writer is D, Scientist Search/autotune. The existing default seam
is `scientist/methods/autotune/runtime.py::SearchLoopRunner.run`: it takes
`SearchLoopSpec.candidate_generator` and passes it into `SearchController`, then
`_NativeSearchServiceDriver.run_search`. E did not edit those owners.

## Delivered contract and actual witness

`SensitivityBridge.analyze_search_space(bounds, evaluator, method=..., seed=...,
input_law=..., store=configured_store, max_estimated_runs=...)` uses the canonical
SALib producer, executes each actual row, and returns the existing `analysis_ref`.
The CAS kind is `doe_sensitivity_analysis`, schema `1.0`. The receipt contains the
full plan, ordered X/Y, complete denominator and numerical result; it is not a
population-law or evaluator-provenance attestation.

`SensitivityAwareCandidateGenerator.from_artifact(base_generator, configured_store,
analysis_ref)` resolves kind/schema/hash and recomputes the numerical analysis.
Its single/batch candidate outputs preserve `_sensitivity.analysis_ref`,
`design_id`, `analysis_id`, method, ranking and exploratory purpose. This decorator
currently enriches metadata; that alone does not establish that default Search
uses its ranking to change a proposal or an optimization decision.

The reproducible witness script is `../doe_block_replay_witness.py`. It drives the
actual bridge with dimensionless x,z in [0,1], explicit independent experimental
law, seed 31, 1024 complete Saltelli blocks and a 6144-run budget. Actual evaluator
calls are 6144. For y=x+z+2xz, independent ANOVA gives variance components
1/3,1/3,1/36 and total 25/36; S1=(12/25,12/25), S2=1/25,
ST=(13/25,13/25), absolute numerical tolerance .01. A new process reopens the CAS,
uses the existing reader in single and batch paths, and rejects an integrity-valid
receipt with forged S2=.99. Complete deciding outputs are adjacent.

## Minimal D inputs and next result

Supply the actual admitted Search-space bounds/distribution/units in the existing
loop's parameter coordinates, its real evaluator and purpose, explicit seed,
budget, and the same configured store used by `SearchLoopRunner`. For Sobol,
declare the independent parameter experiment; a dependent/unknown input law must
refuse before evaluator execution. A declaration is not evidence of population
independence. No production history is needed to prove this generic wiring.

Reuse the existing spec rather than creating another loop. The applicable wiring
is to produce `analysis_ref` through `SensitivityBridge`, resolve it through
`from_artifact`, and replace the existing spec's `candidate_generator` with that
resolved decorator before the native controller is created. D chooses the
existing persisted Search state/result field that carries the exact ref and
declares which actual proposal consumer applies the ranking. Do not silently
promise behavioral focus merely because metadata is present.

The next deciding result is a default `SearchLoopRunner`/native driver witness
whose executed candidates and persisted/reopened state contain the exact ref and
computed identity, and whose intended ranking-dependent behavior is observed.
Changing the evaluator's interaction must change the recomputed sensitivity used
by that consumer. Deleting the call/decorator while leaving metadata markers must
break the witness. E's numerical and reader tests provide the upstream packet;
D's default-caller test completes the bridge.

Required negatives: unknown/dependent Sobol law and missing seed give zero evaluator
calls; stale receipt after whole paired-block reorder, integrity-valid forged
index, wrong kind/schema and wrong distribution/seed refuse at fresh readback.
Within-block role changes and duplicated/missing blocks are invalid. Whole valid
blocks may be permuted together with Y: point estimands remain equal, while
ordered content/design/analysis IDs change and the old receipt is rejected.

## Decision boundary

Runtime block membership, computed quantities and receipt readback are `recomputed`.
The finite fixture oracle is independent analytic truth. The production evaluator,
population law and default Search call remain `not_established`; no causal,
treatment or policy authority follows. B97–B105 retain their committed partial
ledger status pending individual accountable-owner acceptance. This packet adds
verification evidence; it does not batch-ratify the findings.
