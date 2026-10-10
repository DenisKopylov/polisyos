# Independent static review: Q2 installed read-API companion r3

**Disposition: GO to apply r3 as a plan-only correction; NO-GO to execute Q2 until the exact final source freeze and input rebinding are supplied.** R3 fixes the r2 facade mismatch with a selector that tests the requested Core contracts export. No tests, collection, build, install, Docker operation, or Git command ran in this review.

## Inputs and exact readback

- R3 patch `LOCAL/q2-packaging/raw/q2-installed-read-api-companion-r3.patch`: SHA-256 `1e209d9a8aaced4b13ddc0934f955f708cc7311b5c92e4f42d996586d50ec45d`.
- R3 author note `LOCAL/q2-packaging/q2-installed-read-api-companion-note-r3.md`: SHA-256 `961c4d290c967d39b7473d0899c2e3afaa58c6d49bc525576638d2e6224f9a4a`.
- Root-supplied current source identity is `4123b31bdb84ffc39f9c356a47a3360ebc55182d` / tree `8e0277…`; it was not re-derived with Git.
- The five changed paths’ unified-diff preimages matched the present files when checked in memory. The calculated postimage hashes match the r3 note exactly: manifest `1656e209631d8fa401ed65a87c8fff90e07f5996bf8435da4f860e2dc987f277`, runner `a64bab2a692e9f3a88b0693887a430aa3ee2f78e2ca4fa847ed5871ec0c7a3b0`, timeout driver `0f6ae40c5fa0a9959718b6eb365c3fa3f4ad172fbae565702c3be357759be312`, Linux helper `9241d6d695a27e673cd36f6416cfbf03fbc1c383368d642827d7380cfbc71d81`, and recipe `8b56d6053cc02f5d81e990bd3e93214e5802bfcc98cc61dab57ceb99daf2ab96`.

## R2 finding and r3 correction

R2’s second selector checked `polisyos.data_forge.read_api.catalog.CatalogRunProfile` against the Data Forge domain type, not the Core contracts facade. That was a P38 mismatch: the measured neighboring export could pass while `polisyos.core.contracts.CatalogRunProfile` remained absent. R3 replaces that selector with `tests/repo_quality/architecture/test_public_surface_export_resolution.py::test_catalog_run_profile_is_exported_from_core_contracts_facade`.

The replacement test exists at the declared path with SHA-256 `5bc483ddc2ff56b75d5b5766ead17b34b92adb5e10bb1777fe1baa52e77085c5`. Its body imports `polisyos.core.contracts` and the canonical `CatalogRunProfile` from `polisyos.core.contracts.control`, then checks `__all__` membership and object identity. The other new selector checks the installed Data Forge read-API facade’s `__all__`, `dir`, canonical normalizer identity, and `DEU -> DE` behavior. Both are semantic positive controls, not marker-only assertions. The wheel configuration includes `tools`; the architecture test’s `tools.devx.architecture.guardrails` import is therefore within the declared installed package surface, subject to the still-pending runtime origin proof.

## Quantity, runner, profile, and freeze checks

I independently recomputed the proposed selector set from the current 125-ID manifest plus the two r3 node IDs: count **127**, digest `db4d5f6de32b75956418db780b50d043fc08b7c92a543b056731c34e3bdd873d`. The five baseline test paths plus four additional consumer test paths give nine source-hash entries; all nine declared hashes match their current files, including the new Core test file. The historical subset is still 100 IDs / `a1da373ad502cb17fe1932757cae15fd91450063587720e1ec727e32676f751b`; the manifest retains all 11 force-included assets without changing their declarations.

The generic `additional_installed_consumers.values()` argv loop now dispatches the added groups without a per-group special case. The historical-subset builder remains scoped to its original two groups, preserving the historical 91-plus-nine set. The Q2 runner loops over the three named profiles and, for each, verifies exact collected/JUnit IDs, zero skips/failures/errors, installed package origins, and that neither the frozen nor live source/test roots entered `sys.path`. The Linux wrapper requires all three profiles in the primary receipt and six supplemental selectors per profile. These code paths establish planned checks only; none has executed on the final source.

The Linux helper changes only count wording and pins. Its owned-worker-bare admission block remains before attempt-output creation: it rejects a missing or indirect origin/store, requires the exact recorded worker-bare origin and bare-store status, checks requested SHA/tree/branch and shallow boundary, and rejects external alternates. All updated runner/manifest hashes agree across timeout driver, helper, and the candidate note. The patch does not change the existing candidate baseline source SHA or replace `candidate_baseline.source_tree: REQUIRED_FROM_FINAL_FREEZE`; no final freeze SHA is assigned.

**P40 bucket:** same class one level deeper—installed public-facade export/identity coverage. R2’s wrong-namespace selector is corrected by the source-backed Core consumer; the generic consumer-group mechanism covers the added quantity. Keep the historical 100-ID denominator and force-include denominator separate from the 127-ID current set.

## Remaining gate

R3 is a plan/preparation delta, not a Q2 result. Root must bind the final commit/tree, regenerate and review the complete source/input manifest, and confirm the installed environment/worker inputs before the single serialized Q2 wave. Apply and read back the five-file postimage first; then run the planned static AST checks before the final freeze. No success or finding closure is claimed here.
