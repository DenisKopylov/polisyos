# E DOE delta: current runtime evidence

**Verdict:** the 7537 documentation delta adds no DOE/posterior-profile runtime or test result. The earlier bounded DOE/CAS GO remains valid for its reviewed unchanged path; the new posterior producer → CAS → current Scientist consumer profile remains **UNRUN / not established**. This is an evidence gap, not a newly observed source defect. No tests were run in this review.

## Candidate and scope

- Pinned ref `origin/codex/e02-E-doe-20261006` is `7537ef95beed07d02a3b72343b082ff3b7fd14e2`, tree `46a538e5edf82f938547a23ea0b1774ded07697a`; base `43f6bb54e316ce1308d53ba75c6e27e40171e364` is an ancestor. The pin is in `_build/e02-g-continuation-20261006/R/incoming-20261007-1146/pins.json`.
- Its complete delta is 191 paths, all under E02 implementation handoffs: 0 `policy-engine/src`, 0 `policy-engine/tests`, 0 release fragments. The source/test trees are unchanged from 43f; the referenced 64d execution source has the same source/test paths as 43f. The new commit itself is a publication of receipts/docs.
- `frozen-successors-64d.json` names `64d7444a18c55df7b88b71b7699a2f1b25ca24bd` as execution source and `c8054bb2f055fae5f94012773ab4d2efad8cfab7` as document-publication candidate. Keep these identities distinct.

## What the new receipts actually establish

- `frozen-successors-64d/README.md` reports 21 nonshared checks (7 PASS, 14 FAIL) and the separate CI08 run. The recorded CI08 command is `tools/quality/validation/check_extension_examples.py`, not a posterior/DOE profile selector. Its JUnit contains 8 extension-example smoke cases, all passing; `actual-smoke-xml-recompute.json` binds those same eight cases. The native receipt records `finding_closure: false` and backend capability as `SKIP/UNRUN` where applicable.
- The other 21 commands are independent health, debt, architecture, docs, lint, and inventory checks. Their exact `standalone-*.json` receipts bind them to 64d; none invokes the new profile tests or the producer→CAS→D consumer path. A test count or metadata/source inventory is not a runtime witness for that property.
- `continuation-20261006/common-wave/pytest-mc-joint-law-support-and-scientist-consumer.json` is an older 297-pass run at candidate `58e2d97965c0826c44843a78dcb2f8698d9950a3`. It predates the posterior-profile source/test additions between 58e and 43f. Its one legacy `test_propagate_uncertainty_node_updates_simulation_result` case and prior joint-law controls do not execute the new profile producer/readback assertions.
- `continuation-20261007/common-wave-wrapper/bounded-controls-v8/bounded-wrapper-preparation-review.json` is a prepare-only result against `8fa11f569ebb2c952948e09d4db5c1f37be84b83`; it explicitly labels actual native IR inclusion UNRUN. It is neither a test execution nor current-candidate evidence. The v3 observer also failed the intended IR-inclusion assertion on that historical candidate.

## Carry-forward evidence, narrowly

- `continuation-20261007/morris-analysis-work.json` binds the DOE/Morris suite to `5840d477346912b0502689a3eeeb6504e6bc2711`: 221 passing family tests and an 11-case independent candidate oracle. Its property-removal probe fails as required (four native rows are admitted against a two-row plan after removal). The earlier full review checked the relevant later DOE blobs and found them unchanged at 43f except for the separately reviewed Core-import/caller deltas. This is positive evidence for the DOE/Morris sampler/analyzer/admission route, not for the posterior-profile addition.
- `E/core-import-route-r3.json` binds 114 passing affected-consumer tests to matching postimages and records 3 independent route tests plus the expected failing route-removal control. This supports the existing Core CAS/facade route and exact import-alias delta; it does not exercise the new posterior-profile writer/reader or current D consumer with profile-bearing artifacts.
- These receipts remain usable only for their exact tested source/test blobs. They do not become a 7537 PASS for the different profile property by ancestry or shared CAS infrastructure.

## Remaining deciding check

On the exact 7537 source/test tree, run and retain fresh command, environment, full output, and JUnit for:

```text
PYTHONPATH=src python -m pytest -q \
  tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py \
  tests/unit/ir/test_posterior_summary.py \
  tests/unit/scientist/nodes/test_propagate_uncertainty_node.py \
  tests/unit/scientist/nodes/builtins/simulate/test_welfare_empirical_law.py
```

This is the minimum source-defined producer / CAS fresh-read / current-consumer family identified in the prior 43f review. It includes a producer calculation, content-bound CAS readback, named-mean-vs-median and paired-row consumer outcomes, plus forged/incomplete profile and raw-envelope refusals. Do not substitute CI08, a prepared selector, or the earlier 297-case wave. Preserve the prior limitation: profile metadata/context remains a bounded non-gating input (`gate_eligible=false`); the existing evidence does not establish independent estimand/unit/scale identity or default Search-service wiring.

**Pattern classification:** same evidence-gap class as the prior PARTIAL profile verdict, not a new code class (P40). P29/P32/P37/P38 require actual producer→artifact→bridge→consumer outputs and adversarial controls; on the new profile path those execution predicates remain `not_established` until the targeted run is source-bound.
