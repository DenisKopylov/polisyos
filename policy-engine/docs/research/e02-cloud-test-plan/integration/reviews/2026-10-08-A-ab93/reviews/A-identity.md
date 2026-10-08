# A intake identity and footprint review

**Disposition:** identity checks pass for the immutable A candidate and all 18 top-level committed A handoff JSONs. This is an ancestry/input-footprint finding only; it does not accept code, validate runtime semantics, or close E02 findings.

The pinned candidate is `ab93e222381372c54056b9f05e6c8cd7aedf2f2c`, tree `ee92f0719be5b02e212947dcd35f90a1276e875f`. It exactly matches `A-new-pin.json`; `332ba0b91e9a85774d48d101d4af86e3a3baf911` is its ancestor. The complete 332→ab delta is **270 paths: 5 production files, 12 tests, and 253 committed A handoff/evidence files**. Every code/test path differs from G's current `c7adfde6d039e47b1f304eff79340e31a9426270` blob (where present); for these paths G still has the main-baseline blob. The full topic tip is not a checkpoint descendant: its merge base with G is published main `198076863e143dea9f89f02734b13d50dae3eed5`. Treat `ab93` as a carrier with new source deltas, not as a 270-path integration slice.

The latest source-introducer commits below are actual ancestors of `ab93`, their source trees resolve in Git, and each changed file's blob at its last source commit matches the final A candidate. Those commits are A-owned: A-W01 for the CYC/SIM/EMP runtime families; `structure-context-forwarding` is SEL-01/A-W04. Source-specific runtime review and deciding-output interpretation remain separate.

| Final changed source path | Last source commit | Tree | Final blob |
|---|---|---|---|
| `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py` | `6f35cc556be70d84851eb3ac0c5600326ba5a692` | `fc4976eccf3fbd78db4a3bbebfda6591e65866ec` | `1e735f2322a1f15fc8cb6a439d8231b2dc19c898` (matches source commit; G matches main baseline) |
| `policy-engine/src/polisyos/runtime/quality/_generation_cycle_history_schema.py` | `6f35cc556be70d84851eb3ac0c5600326ba5a692` | `fc4976eccf3fbd78db4a3bbebfda6591e65866ec` | `8342187ff3948200fc2515757dad14a1fdf00a4d` (matches source commit; G matches main baseline) |
| `policy-engine/src/polisyos/runtime/quality/conditional_simulation_replay.py` | `975a3b2b97979f36c0af5d2ea98e757e2fe88c99` | `44c5abb9245f975f1e4c29f79cd41796558b9504` | `fe8696e7111b1c6354c1e996dea282291b814b1e` (matches source commit; G matches main baseline) |
| `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` | `0539d6ac1f01614ddb8cbeb7334679bee54231be` | `7bcc4d065c7f6615540bfaf204529b60bdb01b4b` | `18f6cbc8cf3fe2e44ba6d0ed944bf6420d970d0d` (matches source commit; G matches main baseline) |
| `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py` | `975a3b2b97979f36c0af5d2ea98e757e2fe88c99` | `44c5abb9245f975f1e4c29f79cd41796558b9504` | `cb6b7ea4b03e7d90c76f75f8672c03ebb9bdc8cb` (matches source commit; G matches main baseline) |

The N6 history identity mismatch reported against the earlier A332 review is corrected in this pin: source candidate `0539d6ac1f01614ddb8cbeb7334679bee54231be` (tree `7bcc4d065c7f6615540bfaf204529b60bdb01b4b`) and test candidate `f029201ee6162065757486b21058ee85badd057f` (tree `7d3b1795b7760d6b30ddc37f34426452f63b6415`) are both ancestors of `ab93`. The N6 source and history-test blobs read at `ab93` match the named candidate blobs exactly. This repairs identity only; the independent property/evidence reviewer owns the N6 behavioral verdict.

The top-level receipt matrix below records each immutable base and candidate/tree; validated pins and explicitly recomputed footprint entries are in the adjacent ignored JSON. The footprint column is `total (src/tests/companions)` where the handoff records a full snapshot range.

| Handoff | Slice | Base | Candidate / tree | Full snapshot | Source commits | Identity |
|---|---|---|---|---:|---|---|
| `B30-owner-census.json` | B30-owner-census | `f5cfba1e` | `d273659a / eb272482` | — | e2f530b9,d273659a,4c914960 | ok |
| `candidate-purpose-fresh-get.json` | candidate-purpose-fresh-get | `178aae96` | `8856ca1e / 4a4d6fd4` | — | d67630da,1d519572 | ok |
| `conditional-interaction-history-readback.json` | conditional-interaction-history-readback | `332ba0b9` | `9e4753f1 / b20c0656` | 6 (2/4/0) | 75115a02,6f35cc55,be29c75b | ok |
| `configured-n7-resolver-current.json` | configured-n7-resolver-current | `9a4321da` | `9e4753f1 / b20c0656` | 481 (18/34/429) | e74decd8 | ok |
| `coupling-composition-current.json` | coupling-composition-current | `57978875` | `9e4753f1 / b20c0656` | 486 (20/36/430) | 04767a85 | ok |
| `full-queue-progress.json` | coverage manifest | `19807686` | `—` | — | — | — |
| `interaction-history-epochs.json` | interaction-history-epochs | `7f28de05` | `8856ca1e / 4a4d6fd4` | — | 6f35cc55,be29c75b | ok |
| `monetary-producer-decoder-input-gap.json` | monetary-producer-decoder-input-gap | `4ef715ef` | `4ef715ef / b6fddbfb` | — | — | ok |
| `n5-refusal-core-readback.json` | n5-refusal-core-readback | `ad99c27b` | `16d0b70c / 82268b94` | — | 975a3b2b | ok |
| `n6-terminal-projection-history.json` | n6-terminal-projection-history | `93a6c61d` | `f029201e / 7d3b1795` | 3 (1/2/0) | 0539d6ac | ok |
| `partial-recursive-checkpoint.json` | recursive-partial-checkpoint | `33bad45c` | `65926cb5 / f6466a79` | — | 01e465e2,02aff519,7b85f564,9702b5a0 | ok |
| `persisted-value-hard-feasibility.json` | persisted-value-hard-feasibility | `7cdac9c5` | `6c214bde / 6d0dcfc5` | — | 58ff1ccb,4586393e,f5cfba1e,6c214bde | ok |
| `physical-cache.json` | physical-cache | `905820ce` | `9794b716 / 97a03bca` | — | 9794b716 | ok |
| `registered-fallback-n5-n8.json` | registered-fallback-n5-n8 | `b7ec8d8d` | `4bea6bea / 3cebd1c9; extra 06624182` | — | — | ok |
| `required-numeric-output-intake.json` | required-numeric-output-intake | `9e4753f1` | `814a9cbc / 441fd4a6` | 68 (2/5/61) | dc42aec2,6aae70eb | ok |
| `s10-resolver-reason-preservation.json` | s10-resolver-reason-preservation | `4ef715ef` | `0aba32b8 / f3de7250` | 180 (2/4/174) | e9afad87 | ok |
| `sparse-owner-v2-intake.json` | sparse-owner-v2-intake | `aaa89a69` | `4ef715ef / b6fddbfb` | 149 (1/5/143) | 69b607ed,4ef715ef | ok |
| `structure-context-forwarding-current.json` | structure-context-forwarding-current | `e74decd8` | `9e4753f1 / b20c0656` | 478 (16/33/429) | 33a27186 | ok |

The pinned handoff trees and named source/test commits are present and ancestry-valid. Recomputed handoff snapshot counts match their declared complete denominators where provided. Examples of large snapshots (configured N7, coupling, recursive partial, numeric intake, S10, sparse owner, and structure forwarding) explicitly include neighboring slices; their complete counts are not mechanism ownership. Use each receipt's source commit and owned paths to route review.

One concrete evidence limitation is the B30 continuation delta: its exact source change is `4c91496035ccd7285a9539fd6a14d945d568e64b` on `generation_cycle.py`; the complete e848→f1df execution snapshot is 4 paths (2 source, 2 tests), with the second source/test pair identified as adjacent numeric intake and the B30 census test unchanged. The receipt's `source_review` records only an owner-reported “two independent atomic GO” and says the source-review registry has no B30/4c914 row or reviewer artifact pointer. This is a review-evidence limitation for B30 disposition, not an identity mismatch or a blanket rejection of the A candidate: that receipt alone does not establish independent review.

No source, tests, branches, refs, or checkouts were modified. The machine-readable checks are in `A-identity.json` (ignored local inventory; the immutable source pins above remain the transport); the file is ignored under `policy-engine/.gitignore`.
