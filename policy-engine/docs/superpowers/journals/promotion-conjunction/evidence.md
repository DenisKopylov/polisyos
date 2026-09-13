# Promotion conjunction — evidence index

The implementation commit and final attached-branch readback are named in
`execution.md`. Original Stage 1 inputs are `path@28b8a1a420e746b54fbd0b87f73fad1fc4821ba5`;
delivered source/test/probe inputs use the implementation SHA in that handoff.
These relative raw links resolve within this local worktree; outputs are deliberately
gitignored and retained on this machine. Hashes are SHA-256 of complete output bytes.
Expected failing inner tests are distinguished from successful probe-runner results.

No aggregate green is inferred from the first wave or from an unmeasured status.
`epoch-baseline.txt` and `pc-b3-targeted.txt` contain earlier partial dots without
captured process completion: explicit nonreceipts, not deciding passes. Import samples
are debugging observations only. The first trust-probe import was interrupted after
its timeout estimate was found to exclude import time; v2 uses an explicit 1800-second
whole-wave timeout. Targeted test/probe operations use measured runs with a 3600-second
bound; architecture completion was observed within its 3600-second monitoring bound.
The ledger's first run was not timed exactly; its retained actual process code is 0.

| Complete output | Actual code / interpretation | SHA-256 |
| --- | --- | --- |
| [raw/admission.json](raw/admission.json) | 0; Read-only worktree admission immediately before creation | `5292859cd73549fab6689bb7d5f711ace406d3f254346543f338cfe2d7a3681e` |
| [raw/census.json](raw/census.json) | 0; Task-zero base census; complete selected AST and lexical cross-check | `34d6881dfc5eb588f977af68a2c6a6c5bd9ab9db334327875715af85ca56ef6b` |
| [raw/stage1-targeted.txt](raw/stage1-targeted.txt) | 1; Original scope fixtures failed before guards; PA1 controls passed | `69afcfd9b03022ca50c7326fd1c698847d79bcd706d6ee58ccd2e31b642bf401` |
| [raw/stage1-base-replay.txt](raw/stage1-base-replay.txt) | 1; Exact slice-base replay; P41 disjointness not established | `69afcfd9b03022ca50c7326fd1c698847d79bcd706d6ee58ccd2e31b642bf401` |
| [raw/stage1-branch-readback.txt](raw/stage1-branch-readback.txt) | 0; Committed Stage 1 attached-branch readback | `a9e938c00f7968a2e24ec46f8d0fe3482893f9b5802a601c0a88e33d194846ac` |
| [raw/epoch-bridge-red.txt](raw/epoch-bridge-red.txt) | 1; Pre-bridge epoch controls | `f2982fc717f9fc5d9d77db453c1077aaed9fff3f995d8ecf691016c432617124` |
| [raw/pc-b3-red.txt](raw/pc-b3-red.txt) | 1; Pre-custody protected-purpose control | `6243e4ed9955d27d7c5d5c097d1fdc37e1bdc03e8f96a979d800a874c33e3269` |
| [raw/bridge-initial-regression.json](raw/bridge-initial-regression.json) | 0; Initial existing admission/core regression controls; captured process output | `9e6e7e3f43d30a32df48a24e7e1a136f81dbafcc03798e6fbac4353d5802ca8b` |
| [raw/bridge-targeted.json](raw/bridge-targeted.json) | 1; Intermediate B2 source/reference failure output | `4cd09c1a76cd72d4e3d0f5e6964bd526ff9a0b56835e4fc862449d5918c29afc` |
| [raw/bridge-targeted-v2.json](raw/bridge-targeted-v2.json) | 1; Intermediate B2 source/reference failure output | `4e4930f7c3f0489effdd3549989b8c0ad6049877df6012c02fc485da2b091742` |
| [raw/scope-guards-first.txt](raw/scope-guards-first.txt) | 1; Initial negative-receipt fixture failure | `d78a5a54900d8d2b42ec3e8be659b3418a2b3dd417aa81653a15ee383ff7a82b` |
| [raw/scope-guards.txt](raw/scope-guards.txt) | 0; Independent original-guard baseline | `54a7f0500c37950ee184bcfa135a407123398a608d14959c297e596cc3d58e71` |
| [raw/final-targeted.txt](raw/final-targeted.txt) | 1; First targeted wave; retained owned fixture failures | `99ce0467e9648264117a2a86c8caf57d45b83347d832a0a4d34028dd3e66431a` |
| [raw/repair-targeted.txt](raw/repair-targeted.txt) | 0; Complete bounded repaired caller selection; exact selectors in repair-source-freeze.json | `41a84fe9c80ccf1a948bbaacfe2bf8458fe8106fd24dc7c5599a1c3c513ec7d0` |
| [raw/scope-removal-wave.txt](raw/scope-removal-wave.txt) | 0; Original-anchor removal runner; each intended inner pytest result is 1 | `49435c8c6d0cd6007557d5d49072687a5a0be7a71e5e32a22f6c0b64e61ddad9` |
| [raw/removal-constructor.txt](raw/removal-constructor.txt) | 1 (expected); Original constructor guard removal and exact call-phase failure | `729068b79620e27410d9ecc88b5f4c6777a83b29cd68f88f40b2c92d1239a25d` |
| [raw/removal-semantic.txt](raw/removal-semantic.txt) | 1 (expected); Original semantic-scope guard removal and exact call-phase failure | `259a4da51a3b254c24e0de265cff847d49f3a523901d9a8eb20b088cde8ea243` |
| [raw/removal-authority.txt](raw/removal-authority.txt) | 1 (expected); Original authority-laundering guard removal and exact call-phase failure | `7b9c4bac69d5497cf10a1d192bf50409af5565404852f7eb1cc8cfb637dc7c67` |
| [raw/epoch-removal-wave.txt](raw/epoch-removal-wave.txt) | 1; First epoch harness missed the preimported alias; not a passing removal receipt | `7878ccf0ef74a6a3d230ca83064e832fe69aebf38871f43e42f23b02f8c10367` |
| [raw/bridge-removal-wave.txt](raw/bridge-removal-wave.txt) | 0; Source/resolver/mode removal runner; each intended inner pytest result is 1 | `fe5032f499d1ae514f796b8272019ecb929cf6804cbfb63e8d15a6f4f82dc0ad` |
| [raw/repair-wave.txt](raw/repair-wave.txt) | 1; Aggregate retained: targeted and scope/bridge probes passed; first epoch harness failed | `37bdf9a1b4575f23cb8d3c01f767492f1ca38dc6eea202b38079fa05b5059e76` |
| [raw/census-delivery.json](raw/census-delivery.json) | 0; Delivery census; same fully qualified helper-return predicate | `705caba8ff9ef38ff043987f0e48f05286435493b6e1f638917cd9978d357887` |
| [raw/posture-census-delivery.json](raw/posture-census-delivery.json) | 0; Complete source Python AST constructor census; dynamic dispatch unresolved | `0a576f26e28825f20e6d3cef02fc48a5b82e499e09abf5d83ff9844e7cc5b822` |
| [raw/lint-delivery.txt](raw/lint-delivery.txt) | 0; All changed Python at source freeze; exact selected argv in lint-delivery.receipt.json | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| [raw/lint-trust-probe.txt](raw/lint-trust-probe.txt) | 0; Added bounded trust probe lint | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| [raw/trust-register-write.txt](raw/trust-register-write.txt) | 0; Canonical owner writes only required trust JSON companion | `9465108d336f7d74849d0247e1ba1da14c49bdc0d9e25c1215e8491c6d67fb40` |
| [raw/trust-register-check.json](raw/trust-register-check.json) | 0; Full live owner recomputation matches committed-format companion | `020d8e368ef2f5cb8121f77a24349b6f4167765195384c1fdcd0d977a4763a8c` |
| [raw/trust-source-drift.txt](raw/trust-source-drift.txt) | 130; Interrupted initial import; explicit harness nonreceipt | `c4d2a3d432fafca4f1290f53b2ffae6f0b9ad61d129c304cba57b7525cb312e6` |
| [raw/trust-source-drift-v2.txt](raw/trust-source-drift-v2.txt) | 0; Original owner returns 0 before mutation and raises exact DS11-GENERATED-DRIFT after source-byte mutation | `8e1981402d20598db24d776bebcd116084db3bae3e50c75bb88c361b2d2dd689` |
| [raw/guardrails-final.txt](raw/guardrails-final.txt) | 1; First architecture invocation; lane snapshot contamination and generated drift | `e5fdb9ed998440450e28457329d879b63841d77188ffdb677da37bc645012a53` |
| [raw/guardrails-frozen.txt](raw/guardrails-frozen.txt) | 1; Frozen architecture invocation; only named OpenAPI snapshot mismatch | `94fca807719d6c44ae59ee3a18476d4be4e087eb44385801faddc03eec336078` |
| [raw/ledger-final.txt](raw/ledger-final.txt) | 0; Registered check alone; temporal scope described in PC-E04 | `27ceefbcaca3ade0bf55a2f042e48dbf2dcc6f3d9698aec09491fd59336bb683` |
| [raw/ledger-selector-delivery.json](raw/ledger-selector-delivery.json) | 0; Complete current owner-derived selector identity compared to earlier budget | `5a5d1d434882a0a9d47350531bce1ebb4ce3906d2e41afa30520fa44d2865ceb` |
| [raw/epoch-alias-recheck.txt](raw/epoch-alias-recheck.txt) | 0; Baseline before/after passed; each corrected forwarding removal produced its intended call failure | `61dd8f912533043050dbffab018066b9e727125d2cc53e41fcbb1ce9a88544e0` |
| [raw/epoch-alias-recheck.receipt.json](raw/epoch-alias-recheck.receipt.json) | 0; Actual supervised process completion including imports | `23361ff99625bc98dc4c9eb1f0602d24eaa4c44b4ce44454a47146193c055d38` |
| [raw/epoch_removal_probe_first.py](raw/epoch_removal_probe_first.py) | input artifact; Exact preserved first harness; explains module-attribute alias miss | `d46eace9e85ddd0d29c31da78cd045489acfca14e95ac95296389712d989e7a0` |
| [raw/lint-closeout.txt](raw/lint-closeout.txt) | 0; final complete changed-Python selection including corrected harness | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |

The source-read boundaries, full selected sets and independent cross-checks live
inside their respective census/owner/probe outputs. Counts are intentionally not
summed across overlapping test selections. Full refusal-marker outputs are kept,
not replaced by their pytest exit codes.
