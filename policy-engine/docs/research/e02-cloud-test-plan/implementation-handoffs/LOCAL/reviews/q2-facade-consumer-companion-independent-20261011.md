# Independent review: Q2 facade and public-consumer companion

**Disposition: GO to apply the bounded three-test-path companion if the pinned preimages still match; runtime and installed-profile evidence remain UNRUN.** No product or test files were changed. I did not import product modules, collect tests, or run tests or gates.

## Exact target and evidence

The proposal patch is `LOCAL/q2-packaging/raw/q2-facade-consumer-companion.patch`, SHA-256 `bb2d4dd716cf02b5b135e82f8c96188b7bb695a040aa003ed1106bb18a485ead`. Its explanatory note is `LOCAL/q2-packaging/q2-facade-consumer-companion.md`, SHA-256 `9e420aef9e665a94b3fa6b6df28570247dc632dbcf34408aef260b392c4c75b4`.

The patch has exactly three target paths. Current bytes match all three noted preimages:

| Path | Current/preimage SHA-256 | Proposed postimage SHA-256 |
|---|---|---|
| `policy-engine/tests/unit/fabric/test_semantic_group_imports.py` | `59013de3042b61b14fffb19769864d8ccc686963a478fab5fe7170abce42d968` | `0f3162454ff5b57a451119b62249044108c445a41f28ad07a3dc4e8fd780e611` |
| `policy-engine/tests/unit/foundry/methods/test_artifacts.py` | `8cd23b1a481ece841ef1dd9f202ad41b68c8b09eb3ff59d9730116c3741e357f` | `6c58683b86f279a45be7e0f011d29baa4425bb178a92dde38aa193a4a140bf07` |
| `policy-engine/tests/integration/foundry/uncertainty/test_posterior_summary_persistence.py` | `ae65b7181b58c20c6a7be193b4388b18d3efce8caac8ae8b9bc92b6dd71d98c8` | `383d64bf0491c6e0aec96aa1f44ec573444dc1eb9c902db630e03307707b392f` |

Read-only `git apply --check` succeeded. I reconstructed all three postimages in memory and ran Python AST parsing and bytecode compilation without executing or importing them; each postimage compiled and its SHA-256 matched the note. These are static patch-integrity checks, not behavioral verification or collection.

## Hunk review

1. `test_identity_facade_exports_bind_all_manifest_owners` derives the complete current manifest export set from `manifest.__all__`, or from non-underscore names when `__all__` is absent. It asserts the Fabric identity facade exposes each name as the identical manifest object. It separately derives the facade's declared `__all__`, requires exactly one canonical owner among `manifest` and `segment_manifest`, and checks object identity. This covers the legacy implicit `BaseModel`, `ConfigDict`, `Field`, and `utc_now` exports without hard-coding the export list, plus the segment writer. It is generic over the current owner export sets and does not accept a callable, marker, or locally supplied expected-name list as authority.
2. `test_artifacts_facade_exports_bind_all_parts_owners` derives its denominator from `parts.__all__`, checks the facade list matches, and requires object identity for every exported owner. This checks the full current parts surface, rather than a sample.
3. The integration test changes `MonteCarloPropagator` to the existing `polisyos.foundry.uncertainty` public facade. The existing body runs the registered HMC method, persists method evidence and a selected posterior-summary view to `FileSystemCAS`, reads through a newly created CAS reader, then calls actual joint-row propagation and checks source refs/hashes, selected role, rows, and candidate-only `gate_eligible=False` / `unit_binding_status="not_established"`. The facade source at `e536bab756ca5538b105205f27a627625dd1da72` exposes this name in `__all__` and has SHA-256 `45ace7c8759d468214ceab42dc3a5cfe2c09bba85c5c5a5b9da7079aa76bbf1c`. The proposed route therefore reaches a real persisted consumer path, not an import-only test.

The integration fixture is controlled synthetic HMC data. It establishes no external scientific or policy authority. It creates a fresh CAS reader in-process; the separate existing fresh-process test is not evidence that this changed Monte Carlo caller itself ran in a fresh process.

## Existing source-runtime evidence and limits

The prior retained source-tree command `LOCAL/raw/batched-blocking-focused-20261010/current-full-export-identities-plus-implicit-manifest-20261011/command.json` (SHA-256 `630d35d76f37498b2c4e27bdc30c6d4f395a89974fe6b7aa2fce326c6cbefb2e`) actually imported and checked 243 owner-identity bindings. Its stdout SHA-256 is `afd74c35ce2d7bc846a8766770b18ff6c6ff2973d803a08edcc81d666a8ac4e2`; stderr was empty. The command ran at base HEAD `b3afc367519e4e7d36872b2e4c70b907f03246f8`; both relevant facade files had the exact candidate bytes before and after. Those two facade blobs are unchanged in the published I001-204 source commit `e536bab756ca5538b105205f27a627625dd1da72`. This is real source-tree runtime evidence for those facade bindings, not installed-wheel, sdist, or packaged-client evidence. The new two unit tests and redirected integration consumer have not been run.

The patch note reports two additional test IDs (planned total 195 from the existing 193). Neither collection nor JUnit reconciliation has run; treat 195 as planned arithmetic only. The actual installed profile/origin guard, package build, and full runtime verification remain UNRUN. `MonteCarloPropagator` is an optional-stack export whose facade can set it to `None` on import failure; the intended numerical test profile must provide the supported uncertainty dependencies so the new caller exercises the class rather than a missing optional export. No profile execution was performed here.

## Requirement and risk verdict

- **Specification:** The patch matches the bounded proposal: generic owner-derived facade identity tests plus an existing persisted-consumer route through the public uncertainty facade. No source or schema behavior is changed.
- **Engineering:** No static blocker found. `git apply --check` and in-memory postimage AST/compile checks passed. The three proposed postimage hashes match the note.
- **Residual:** Behavioral tests, test collection, installed-origin checks, and supported-profile execution are still required after source freeze. Do not claim wheel/package compatibility from the source-tree 243-binding check.

**P38:** The protected property is binding public facade names to their canonical owner objects and reaching the persisted uncertainty consumer through the supported facade. The tests assert object identity for the complete owner-derived sets and exercise the consumer body. A divergent installed package/origin or unavailable optional uncertainty stack is not measured by this static review and must be checked in the later installed-profile run.

**P40:** SAME_CLASS_DEEPER. This companion widens the existing facade-binding and public-consumer evidence at these three callsites; it does not define a new closure class. Formal closure remains with the governing review.

**P41:** The proposal is still unapplied and the runtime checks were not replayed here. No result is classified as inherited or green.
