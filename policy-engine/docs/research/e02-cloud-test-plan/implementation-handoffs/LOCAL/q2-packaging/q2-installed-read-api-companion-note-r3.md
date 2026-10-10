# Q2 installed read-API companion — corrected unapplied preparation

This patch replaces the incorrect Data Forge CatalogRunProfile consumer from r2 with the exact public Core contracts facade property. The two selected consumers are:

- tests/unit/data_forge/read_api/test_catalog_graph_builders.py::test_country_normalizer_is_exported_by_catalog_read_api checks the installed Data Forge read-API facade export identity against the canonical country-code owner, including DEU to DE behavior.
- tests/repo_quality/architecture/test_public_surface_export_resolution.py::test_catalog_run_profile_is_exported_from_core_contracts_facade checks polisyos.core.contracts.__all__ includes CatalogRunProfile and that polisyos.core.contracts.CatalogRunProfile is identical to the canonical polisyos.core.contracts.control.CatalogRunProfile.

The r2 selector only compared the Data Forge catalog facade to the Data Forge domain type. That is a different namespace and did not test the requested Core contracts public export; this r3 patch corrects that P38 mismatch without changing the number of selected cases.

The candidate remains 127 selected IDs, with 116 selected IDs from the five baseline paths and 11 declared additional selectors. The named historical subset remains 100 IDs / SHA-256 a1da373ad502cb17fe1932757cae15fd91450063587720e1ec727e32676f751b. All 11 force-include asset declarations and expected bytes/digests are unchanged. The new Core contracts test file has SHA-256 5bc483ddc2ff56b75d5b5766ead17b34b92adb5e10bb1777fe1baa52e77085c5; all nine selected source-file hashes match the candidate manifest. Both new selector functions resolve once without parametrization decorators. No source freeze SHA is assigned; candidate_baseline.source_tree remains REQUIRED_FROM_FINAL_FREEZE.

Static verification only: JSON parsed, the full selected-path/source-hash denominator matched, all nine current selected source-file hashes matched, selected ID count and digest recomputed, and runner/timeout-driver AST parsed. No collection, pytest body, build, install, Docker operation, Git operation, source edit, or package wave was run.

Candidate file hashes:
- manifest: 1656e209631d8fa401ed65a87c8fff90e07f5996bf8435da4f860e2dc987f277
- runner: a64bab2a692e9f3a88b0693887a430aa3ee2f78e2ca4fa847ed5871ec0c7a3b0
- timeout driver: 0f6ae40c5fa0a9959718b6eb365c3fa3f4ad172fbae565702c3be357759be312
- Linux wave helper: 9241d6d695a27e673cd36f6416cfbf03fbc1c383368d642827d7380cfbc71d81
- recipe: 8b56d6053cc02f5d81e990bd3e93214e5802bfcc98cc61dab57ceb99daf2ab96

Patch: LOCAL/q2-packaging/raw/q2-installed-read-api-companion-r3.patch
Patch SHA-256: 1e209d9a8aaced4b13ddc0934f955f708cc7311b5c92e4f42d996586d50ec45d
Patch size: 18485 bytes.

Use this r3 patch; r1 and r2 artifacts remain retained as superseded scratch. The generic consumer argv loop is preserved, as is the owned-bare admission block. Apply and review after root serializes the freeze inputs, then bind the final source SHA/tree and recalculate/review pins before the installed wave.
