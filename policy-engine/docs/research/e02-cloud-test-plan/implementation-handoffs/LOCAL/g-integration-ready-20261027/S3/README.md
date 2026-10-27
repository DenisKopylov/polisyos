# S3: paired identification and native-uncertainty witness

**State:** Published author handoff for independent G review. This records a bounded S3 author-task exit; it is not canonical code acceptance, formal B31 closure, or a G acceptance.

The source snapshot is commit `e22f05ef1b3d70c6ed6de0ead6459f71a8239b8d` (tree `3bb7f3b72fc9bb85474e607e5fffd1a0ae39ef3b`, parent `8c5efa250faa2e983b1ce7a2021b9ea135846a69`). That commit changes exactly the two S3 test modules listed in `packet.json`; their committed blob hashes were re-read and match the worktree. No production S3 code changed.

## What the tests witness

The candidate path is:

`N8 source profile/projection → typed source assignment → method report + candidate identification bounds + execution receipt/run basis → Core CAS persistence → candidate ValueOuterSet → fresh generation_cycle consumer reload and recomputation`.

The paired m/km fixture keeps ID and native uncertainty distinct. In m, ID is `[4, 4]` and CI is `[1, 10]`; in km, ID is `[0.004, 0.004]` and CI is `[0.001, 0.010]`. All four endpoints scale by 1,000, units agree across assignment/report/bounds/output, and estimand specs match after unit normalization.

The negative witnesses reject a symmetric `[1, 7]` report even with lineage markers, a km report/bounds reference rebound into an m basis, missing bounds references, changed source context, unresolved requests, and a removed owner-assignment edge. The raw-manifest adversary changes selected raw panel bytes through the consumed `get_raw_manifest_bytes` seam while typed `get_manifest` remains delegated; it must fail before a forbidden runner call. A separate actual-method witness shows DID and Synthetic Control provenance can differ while resolving to the same owner coordinate.

These are synthetic/deterministic fixtures. The tests keep the value blocked and identify the run as candidate-only; assignment is consumer-asserted and source time is not established. They make no estimator-accuracy, causal-truth, calibration, source-assignment-truth, authority, or publication claim.

## Run receipts (keep separate)

- Initial selected wave: **4 nodes, 3 passed, 1 failed**. The sole failure was the paired test calling `model_dump` on frozen dataclass `EstimandSpec`; the other three nodes passed. Do not recast this result as 4/4.
- Follow-up after the test-only R6 correction: the original paired node alone was rerun: **1 passed, 0 failed/errors** (88.47 s, 1.28 GB peak RSS). This is not a rerun of the whole four-node wave.
- R6's exact test-only patch imports `asdict` and replaces the two dataclass `model_dump` calls. The initial and follow-up readsets differ by the changed test module; the unchanged `test_b31_owner_run_basis_v2.py` matches R1, and `test_value_gate.py` matches R2. Do not describe the whole R1/R2 test-file readsets as equal.

Full audit-result, stdout, JUnit, and readset paths and hashes are recorded in `packet.json`.

## Status and remaining dependency

S3 author-task exit is **GO, bounded to this candidate test witness**. `canonical_code_acceptance=false`, `formal_b31_closure=not_adjudicated`, and `closure_ids=[]`. The original B31 criterion remains open; coverage still says criterion-specific acceptance was not executed and labels the capability `absent/unallocated`.

S3 depends on S1. S1 remains `implementation_remaining`, including separate B161 source-array/unit-scope work. The supplied m/km unit fixture bounds this S3 witness; it does not close or absorb all S1/B161 work.

The G feedback receipt reviewed package `8c5efa250faa2e983b1ce7a2021b9ea135846a69` and contains no S3 disposition. G acceptance for S3 is therefore `not_established`.

See `packet.json` for the source/consumer/test/config footprint, criterion provenance, pattern pass, run receipts, and exact hashes.