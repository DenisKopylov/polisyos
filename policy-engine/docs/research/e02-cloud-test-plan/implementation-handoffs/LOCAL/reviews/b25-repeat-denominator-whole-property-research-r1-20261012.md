# B25 repeat-denominator whole-property diagnosis (r1, 2026-10-12)

**State:** read-only source diagnosis; provisional root WIP, not a candidate freeze or G decision.  
**Author role:** source researcher, not G.  
**closure_ids:** `[]`  
**Checkout:** `codex/e02-unified-local-20261009`, HEAD `512ad7fede6fdc40e86066630fd63df5b2c11161`, tree `887ba4d0e59a604f71409a45bedd0189ca684999`.

No source, index, history, or tests were changed or executed for this diagnosis. The requested local receipt is the only new file. Historical B25, B198, and the full Q0 denominator remain untouched: 282 finding IDs / 291 occurrence rows; B198 remains its own occurrence. The current source freeze and candidate evaluation are not established.

## Occurrence and authority boundary

B25 is `coverage.json#/findings/150/criterion_refs/0`, card SIM-03. Its criterion is bound to `B_r19_original.md` at commit `198076863e143dea9f89f02734b13d50dae3eed5`, blob `d800082eebfc12eaf647b0c0257c4f06e135d25a`, lines 503–516, span SHA-256 `f7e4a5e349589575920d7885587f7cce2b62c0148bf8ef57b7f8b9f684959c81`. The criterion includes required-set comparison, repeat-level per-moment denominators, optional-moment comparability, and the boundary that no real accepted decision was shown.

The pinned coverage file is `policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json` @ SHA-256 `97860dc18c7b92124971aa8032fc229be3367723ea2ec45e6cda4a777e544e01`. Row 150 preserves `ledger_status_historical=closed`, `appendix_c_status_separate=no_finding_level_record`, `closure_now=not_adjudicated`, and historical `capability_label=surface_out_of_scope`; its acceptance note says optional-metric/other-method expansion is not itself a valid proxy for closure. Those fields are historical/source boundaries, not current candidate evidence.

The independent Q0 whole-criterion review is `.../reviews/q0-original-criterion-complement-bucket2-independent-r1-20261012/32-row-independent-review.json` @ SHA-256 `66dac818822ea9509657f797b40171069eb4cdd1474247b21b0f279dde930193`. Its B25 row binds the same occurrence, calls owner alignment `mismatch_partial`, and says the owner's property/next-check cover a missing required moment in one loss but omit per-moment repeat denominators and predeclared optional-moment comparability. The review has every candidate `UNRUN`, no formal closure IDs, and marks final candidate source/input/profile/consumer execution `not_established`.

The owner assessment `.../reviews/full-id-A-assessment.json` @ SHA-256 `4013536c5087c3cb3c90f2563b695f3e57455719efe87c42c85c979f92a649ab` reports 22/22 required-moment regression results from its historical 49-wave and records the exact next step as reconciling estimator/tests bytes to b2cd. Its named historical receipt `implementation-handoffs/A/physical-cache.json` has expected SHA-256 `d266405e3960d090c85a12322faf206667849e581f843546a17ccc907f173a1b`, but that path is absent from this checkout; the 22/22 statement is therefore retained as an owner-reported historical result, not replayed evidence. The bound current-source delta is `.../reviews/full-id-A-current-source-delta.md` @ SHA-256 `4b6db8c7cbc371b83def47662872c3fcd62a35067caef09eef06b042a28318fe` and explicitly leaves current candidate evaluation unrun.

Canonical `TASKS.json` @ SHA-256 `a37c75cfe09d33c1f50379d5bbfd04bdb728c990e832aec3bf19c0d17035734c` routes B25 through Q0. V6 is the separate B13 simulation-persistence task; R4 is the separate B56 competing-study/fold task. Neither is B25 execution or a B25 receipt.

## Source trace and diagnosis

The pinned baseline resolves unambiguously to commit `b2cd1fbb0c9aaa21a05cbf999330a2e07fe81f23`, tree `65c44e4872c0efb0772ee955c2b92351c2486892`. The exact `estimation.py` and `test_estimation.py` blobs at this baseline match the current worktree blobs. The current root-owned `test_sim_03.py` is dirty and differs from the baseline, so a whole-file byte-equality claim for that test is false.

| Source or test | Current worktree Git blob | Relevant behavior |
| --- | --- | --- |
| `policy-engine/src/polisyos/foundry/coupling/estimation.py` | `5f574d9aa735d843722b429bb8c00c3721ca6911` | Required-set distance, calibration, and repeat averaging. Same blob at b2cd. |
| `policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py` | `1f5a597e661069938241c32d2a902974a6d6b390` | Native SMM adapter and repeated simulation producer. |
| `policy-engine/tests/unit/foundry/coupling/test_estimation.py` | `b3240e5acba979af571ac5e8c31998b9b671ec43` | Existing helper test source; same blob at b2cd. |
| `policy-engine/tests/unit/remediation/test_sim_03.py` | `56ba4f214090f0b7ea4026365d88f2c21e64564b` | Root-owned WIP contains required-moment B25 tests; baseline/HEAD blob is `7806d5346225dc3cf1f4bef357100d8889002766`. |
| `policy-engine/tests/unit/foundry/methods/catalog/simulation/test_coupled_policy.py` | `ed02d8620fa70df3bf5db4746d3f1db13499dea8` | Native adapter tests, including best-grid selection and a missing-required-moment block. |
| `policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py` | `9cb503b077dc540dbdb0f7b99494164408f5fd10` | Method-output-to-patch bridge. |
| `policy-engine/src/polisyos/foundry/validation/method_quality.py` | `785c4fe88c2e4a03596ac699b44704d80b147e5f` | Generic method-quality reader of named result refs or `foundry_method_outputs`. |

The actual native source path is `CoupledSMMEstimator.pure_step` → `calibrate_coupled_smm` → one `_run_coupled_policy` call per seed → `extract_coupled_summary`. `extract_coupled_summary` returns a fixed nine-key summary. The native adapter derives its required names from `observed_moments` / `moment_names`, so those same keys are emitted for every seed by this producer; there is no native optional-key missingness control in the current adapter. No simulation or JAX path was executed here.

The required-moment part is implemented at the pinned baseline and current estimator blob: the loss is computed over one explicit required set; a candidate missing any required name gets infinite loss; no finite candidate yields `comparison_status=no_comparable` and `status=blocked`. The root-owned current SIM-03 WIP adds required-moment and all-incomparable cases, but those tests were not run here.

The remaining local helper behavior is narrower and real. `_average_summaries` constructs a union of keys and averages each key over only repeats where that key exists, returning only values. `calibrate_coupled_smm` then constructs `moment_counts` only for required names. Optional keys can therefore appear in `evaluated[*].summary` and `fitted_summary` without their effective repeat counts or an optional-set comparability rule. Required-moment loss selection does not use those optional values, so this source read does **not** establish an incorrectly ranked native candidate. It does establish that the generic runner/result shape can expose optional means whose denominator is not preserved.

For example, with three seeds and the same required value on every run, candidate A can emit optional `wait=1` only on seed 1 while candidate B emits `wait=1` on all three seeds. Both exposed optional means are `1`; current evaluation metadata records only the required count, so the two optional aggregates have indistinguishable output despite denominators 1 and 3. The native adapter's fixed nine-key producer cannot currently produce that missingness pattern, and no accepted downstream consumer of those optional values was found in the source-visible chain.

The method adapter returns a transient `{"result": ...}` containing fit fields and evaluation rows. It does not return `patch_records`. The graph bridge `_append_method_patch_records` only bridges `patch_records`; with declared node outputs it raises a postcondition error, and without declared outputs it records no method patch. The adapter itself does not persist an SMM fit artifact. The generic method-quality reader consumes separately supplied refs or `foundry_method_outputs`; no source link from this adapter result into that reader was established. Accordingly the artifact, bridge, consumer, and API/dashboard/audit surface for a persisted SMM fit are not established here; this is consistent with the historical `surface_out_of_scope` boundary and is not promoted to a capability claim.

## Complete call-site and test census

A read-only Python AST walk parsed the complete `.py` trees (0 parse errors) and enumerated direct named calls, using path and file-type denominators as required by P35:

```text
policy-engine/src:   2,754 Python files; 3 direct calls
  estimation.py:250 _average_summaries
  estimation.py:260 summary_distance
  coupled.py:446 calibrate_coupled_smm
policy-engine/tests: 2,973 Python files; 6 direct calls
  test_estimation.py:42 calibrate_coupled_smm
  test_estimation.py:54 summary_distance
  test_estimation.py:83 summary_distance
  test_sim_03.py:146 summary_distance
  test_sim_03.py:162 calibrate_coupled_smm
  test_sim_03.py:180 calibrate_coupled_smm
```

These are direct AST call sites, not a runtime invocation or import-closure proof. `test_estimation.py` checks best fit and an empty required-set refusal; its repeated candidates return the same keys on every seed. The root-owned SIM-03 WIP tests check a missing required moment, required counts, and all-required-incomparable blocking. The native method test checks a best grid point and missing-required block. None exercises per-moment counts when an optional key is missing on only some repeats, an optional comparison declaration, or downstream persistence/readback.

## Property/proxy and P40 disposition

**P38 property:** preserve the effective denominator for each moment across repeats, and make different optional moment sets explicitly diagnostic/incomparable or compare them only under a declared rule. **Current implementation:** an optional mean is returned while its count is dropped; the code's only gate checks required moment counts. **Divergent case:** same optional mean with 1/3 vs 3/3 repeats, as above. This is an output-truthfulness gap for the generic helper, not evidence that current native required-set ranking chose a wrong accepted decision.

**P40 buckets:** Q0 classifies the substantive estimator-moment/repeat-denominator property as `NEW_CLASS`; preserve that distinction from unrelated source findings. Separately, the omission in B25's owner property/next-check is `SAME_CLASS_DEEPER` of the LA-033 criterion/owner-property binding class. The Q0 review identifies B25 alongside B28 and B71 under that same deeper owner-summary class. On the second same-class owner escape, widen the owner mapping to every original acceptance conjunct, the source-visible producer/result chain, evidence boundary, and row-specific falsifier; do not patch only this next-check sentence. This receipt performs that whole-property mapping for B25 and makes no cross-row closure claim.

The substantive source gap should be closed at the quantity required by B25, or explicitly left as a bounded residual: expose per-moment counts for every returned summary key and declare that optional outputs remain diagnostic-only unless a predeclared optional set/rule makes them comparable. Do not add a generic penalty. A single missing-required test is insufficient.

## Next discriminator and proposed writer scope

The discriminating input is a pure `SummaryRunner` over three seeds: both candidates return `required=0` on every seed; candidate A returns `optional=1` on seed 1 only; candidate B returns `optional=1` on all three. Recompute through `calibrate_coupled_smm` with the same predeclared required set. Acceptance should show `required` counts `3/3`, optional counts `1/3` and `3/3`, and either explicit diagnostic/incomparable status for those optional aggregates or a declared comparison rule fixed before selection. Also retain the existing negative where a required moment disappears and cannot improve the loss. This distinguishes a missing denominator from a selection proxy without requiring JAX.

No writer lease was granted, so no code was changed. If root authorizes the local mechanism repair, the smallest source/test scope is:

- Mechanism: `policy-engine/src/polisyos/foundry/coupling/estimation.py` @ `5f574d9aa735d843722b429bb8c00c3721ca6911`.
- Mandatory pure semantic tests: `policy-engine/tests/unit/foundry/coupling/test_estimation.py` @ `b3240e5acba979af571ac5e8c31998b9b671ec43`; extend existing SIM-03 coverage in the root-owned `policy-engine/tests/unit/remediation/test_sim_03.py` @ current worktree `56ba4f214090f0b7ea4026365d88f2c21e64564b` only under an explicit path lease (it already has root WIP and must not be overwritten).
- `coupled.py` / its JAX-backed test are not required to prove the generic denominator gap: the inspected native producer emits a fixed summary key set. Include them only if the implementation expands the native adapter's declared optional-moment contract. A persisted artifact/consumer bridge would be a separate capability task, not silently included in this local helper patch.

After a writer lease and source freeze, run the pure discriminator and the existing negative with: `cd policy-engine && uv run pytest -q tests/unit/foundry/coupling/test_estimation.py::test_calibrate_coupled_smm_preserves_optional_moment_denominators tests/unit/foundry/coupling/test_estimation.py::test_calibrate_coupled_smm_selects_best_summary_match tests/unit/remediation/test_sim_03.py::test_smm_missing_required_moment_cannot_win_calibration` (the first selector is the proposed new test). No JAX/browser/runtime route is part of this read-only phase. For the native consumer next check, dispatch `CoupledSMMEstimator` as a graph method with its declared `result` output and require the result to survive the graph boundary as an artifact plus fresh readback; current source predicts `patch_records` postcondition failure when outputs are declared and no patch record when they are not. A separate authorized end-to-end task needs a real producer result artifact, bridge, fresh reader, and negative consumer test before claiming a wired SMM capability.

## Evidence and limits

| Evidence | Identity / result |
| --- | --- |
| Original criterion + occurrence | `B_r19` blob `d800082eebfc12eaf647b0c0257c4f06e135d25a`; coverage SHA `97860dc18c7b92124971aa8032fc229be3367723ea2ec45e6cda4a777e544e01` |
| Q0 independent review | `32-row-independent-review.json` @ `66dac818822ea9509657f797b40171069eb4cdd1474247b21b0f279dde930193` |
| Owner assessment | `full-id-A-assessment.json` @ `4013536c5087c3cb3c90f2563b695f3e57455719efe87c42c85c979f92a649ab` |
| Owner source delta | `full-id-A-current-source-delta.md` @ `4b6db8c7cbc371b83def47662872c3fcd62a35067caef09eef06b042a28318fe` |
| Current Q0 owner crosswalk | `occurrence-evaluations-draft.json` @ `82d6fcfe2b8f74b725e51a19467b5aa4a506788f3c7349ae5c41599ba775d339` |
| Canonical Q0 task registry | `TASKS.json` @ `a37c75cfe09d33c1f50379d5bbfd04bdb728c990e832aec3bf19c0d17035734c` |
| Historical closure receipt | Expected `physical-cache.json` SHA `d266405e3960d090c85a12322faf206667849e581f843546a17ccc907f173a1b`; locator absent in this checkout |
| Candidate/runtime evidence | No tests, JAX, numerical simulation, heavy suite, server, browser, or persisted consumer run performed; candidate `UNRUN`; formal closure IDs `[]` |

The occurrence-evaluation digest above is the current-worktree SHA-256 readback. This receipt is a source diagnosis only and does not alter historical closure or make a G claim.
