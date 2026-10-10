# Retrieval scope V4 test-fixture repair — unapplied patch

State: **patch only; not applied; no tests rerun**. This companion addresses two fixture failures from the actual V4 consumer-module run while preserving the production source-admission guard.

## Deciding run and source boundary

The deciding run was the 75-case consumer-module command captured in `LOCAL/raw/retrieval-scope-v4-actual-consumer-modules-verification-20261010/command.json`: 69 passed and 6 failed (2 ExploreLane fixture signature errors, 4 actual FileTabular catalog source-identity refusals). Full stdout, stderr, JUnit, and command metadata remain in that directory. Their SHA-256 values are:

- `command.json`: `933d03635c6e33f384dcdddb14cb6ba609873758fb763cbdbcb391dbfa003f76`
- `stdout.txt`: `5af3cd3f9465935af8bd9060f3e3ffcb43ab57619a09bab76d36b18dcc83685f`
- `stderr.txt`: `7f9addc9dc244d2da6de5b02b7682cb9df70271528310de3795a279c03761b62`
- `junit.xml`: `8eaeccc69f39eea3a0871c9c69ed23a6703e2cc1b51d6f60bd56ed6be2843374`

The run recorded source WIP base `f52809e8210714131f53c7b90bd53a9215c69d69`. Current readback SHA-256:

- `src/polisyos/fabric/retrieval/service.py` — `20643c33f6e5b879570db44fc298e5305381d58c61d53f3912930860c507e636` (read only; unchanged by this companion)
- `src/polisyos/data_forge/read_api/catalog.py` — `279be779b8a04934193edae581e252fffac0708b8fd2d90307a6312f5b2caae0` (read only; unchanged)
- `tests/unit/fabric/test_retrieval_service_catalog.py` — `16d6949c60c9b28b49f4d05af019ae595b11c1faa429410122bb9e783afe662d`
- `tests/unit/data_forge/read_api/test_catalog_graph_builders.py` — `6493a8ecfe49e718839387940aadea42d4c0c38b594425291b4fb8009dbaa343` (read only; unchanged)
- `tests/unit/fabric/test_retrieval_fetch_custody.py` — `8348f1776ab2e0fda4d74e257a84ceaf83443ce1747bdd6348ffbee24fbc41df`
- `src/polisyos/fabric/retrieval/README.md` — `14b5fa32c5617d19f7874740b5f2b8b3af185eec2e542b02ff7d85bb2d4c3d59` (read only; unchanged)
- `release-fragments/unreleased/2026-10-10-fabric-catalog-scope-filtering.toml` — `6fef95ad93ec69dcc48f854c7e6bcc7a1dcc2f65ab95b402a845cc596dcf5ef0` (read only; unchanged)

The unapplied patch changes only the two test modules: `tests/unit/fabric/test_retrieval_service_catalog.py` and `tests/unit/fabric/test_retrieval_fetch_custody.py`. Patch SHA-256: `055c103fb034d38924e6dc9338cdffed324205b460b4975e899af7225ebaac4c`.

## Findings and repair

Two new ExploreLane controls used `_OneCandidateExplore.discover(self, *, data_needs, limits=None)`, but the actual `RetrievalService` calls the established consumer API positionally as `discover(data_needs, limits=...)`. The patch aligns this fake provider with that real signature; it does not change discovery behavior.

Four FileTabular consumer cases fail before their intended assertions because the fixture creates actual `files.tabular` catalog rows with an empty source identity, and the canonical source registry has no `files.tabular` entry. The source guard correctly fails closed at `_catalog_source_is_enabled` with `catalog_source_identity_unresolved`. The fixture now stamps the exact test-owned identity `recorded_file` on its graph records and supplies a strict `CatalogSourceRegistrySpec` entry matching that identity and connector. The entry is enabled and `transport_ready`/`empirical`, so the existing `prod_full` selection path admits this controlled source. The actual FileTabular connector and local CSV read remain in use. This is a bounded test fixture, not a production registry addition or a source-guard bypass.

## P40 and limits

The ExploreLane issue is a fixture/API signature mismatch. The C05 failures show an incomplete source-admission fixture; the code’s refusal is correct and is not weakened. The V4 69/75 result is not an inherited-red claim: no base replay with a zero-intersection denominator was performed. The remaining proof is the root-owned rerun of the same complete three-module command after this fixture delta, including the counterfeit-chain negatives and real connector source recomputation. No source code, catalog contract, global registry, payload, or authority guard changes are proposed here.

The proposed Python files parse with `ast.parse`. No tests, linters, Git commands, or product-file writes were run for this companion.
