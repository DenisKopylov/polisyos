# Independent review: V4 retrieval test-fixture repair

Result: **GO for application and rerunning the complete scoped consumer suite**. This is a fixture-only static review; the proposed patch has not been applied or executed by this reviewer. It is not a runtime receipt or formal G acceptance.

## Exact inputs and prior failures

- Patch `LOCAL/raw/retrieval-scope-v4-test-fixture-repair-20261010.patch` — SHA-256 `055c103fb034d38924e6dc9338cdffed324205b460b4975e899af7225ebaac4c`.
- Decision note `LOCAL/decisions/retrieval-scope-v4-test-fixture-repair-20261010.md` — SHA-256 `199997d389defea04dd5008e826d51eb3aa15ab9b4b95e1fb7f23f32426491ab`.
- The two current test preimages match the note: `tests/unit/fabric/test_retrieval_service_catalog.py` `16d6949c60c9b28b49f4d05af019ae595b11c1faa429410122bb9e783afe662d`; `tests/unit/fabric/test_retrieval_fetch_custody.py` `8348f1776ab2e0fda4d74e257a84ceaf83443ce1747bdd6348ffbee24fbc41df`.
- I read the retained 75-case run output at `LOCAL/raw/retrieval-scope-v4-actual-consumer-modules-verification-20261010/stdout.txt`. It records 69 pass / 6 fail: two `_OneCandidateExplore.discover()` positional-signature `TypeError`s, and four FileTabular cases failing at `_catalog_source_is_enabled` with `catalog_source_identity_unresolved` because the synthetic catalog records have no source identity. This is a reproduced test-fixture boundary, not evidence that the production guard is wrong.

## Fixture integrity review

The ExploreLane fake now accepts the same positional `data_needs` and keyword-only `limits` call shape as `ExploreLaneDiscovery.discover`; it still deliberately emits its fixed test candidate, so the consumer’s request-scope filter remains the property under test.

The FileTabular fixture adds `source="recorded_file"` to its own graph records and temporarily supplies a strict `CatalogSourceRegistrySpec` with the exact `recorded_file` / `files.tabular` pair. The entry is enabled and has valid `transport_ready` / `empirical` values for the test’s `prod_full` selection. The override is scoped to the fixture context and is restored on exit. It does not edit the product registry or retrieval source guard, mock the DatasetCatalogGraph/C05 binding read, mock the connector, or replace the generated CSV. The actual `FileTabularConnector`, local CSV, graph-builder output, and custody readback path remain in the test.

This controlled registry proves only that a well-formed test source with a matching registered identity can traverse the real consumer path. It does not establish production source currentness, authorize an external source, or claim that `recorded_file` exists in the production registry. Existing refusal assertions and source-change/counterfeit controls are unchanged in this patch; the previously observed identity refusal is made admissible only for the explicit local fixture.

## Review status

No scope guard, catalog contract, production registry, assertion, skip, or test outcome was weakened in the two-file diff. I found no blocker in this fixture repair. Root should apply it and rerun the exact complete 75-case command, retaining stdout/stderr/JUnit and checking the four previously refused custody cases along with the ExploreLane selection controls. The previous 69/75 run is not an inherited-green or closure receipt; no P41 claim is made. Post-patch runtime result remains **UNRUN**.

## Independent runtime confirmation (2026-10-10)

The exact fixture patch was present in the shared candidate worktree at base `f52809e8210714131f53c7b90bd53a9215c69d69`, with SHA-256 `055c103fb034d38924e6dc9338cdffed324205b460b4975e899af7225ebaac4c`. The post-patch test files read back as `tests/unit/fabric/test_retrieval_service_catalog.py` `a110ccb699d23594fdd82f6b471452f35f690e9237170a7bf531e2ef4fd261d7` and `tests/unit/fabric/test_retrieval_fetch_custody.py` `4bc3c119fe4e67f70c2754d22902681f5e2875fd73b940d5df8f995bdd35c366`. The production guard files remained byte-identical to their reviewed hashes: `src/polisyos/fabric/retrieval/service.py` `20643c33f6e5b879570db44fc298e5305381d58c61d53f3912930860c507e636`; `src/polisyos/data_forge/read_api/catalog.py` `279be779b8a04934193edae581e252fffac0708b8fd2d90307a6312f5b2caae0`.

I independently reran all three affected modules from the product root with the local `.venv` and one-thread numerical environment:

`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -l .venv/bin/python -B -m pytest -o addopts= -q -ra --tb=short --color=no --basetemp=_build/e02-repair-fixtures/retrieval-scope-v4-fixture-review-attempt2-20261010 --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/retrieval-scope-v4-fixture-review-attempt2-20261010/junit.xml tests/unit/fabric/test_retrieval_service_catalog.py tests/unit/data_forge/read_api/test_catalog_graph_builders.py tests/unit/fabric/test_retrieval_fetch_custody.py`

Result: exit code `0`, `75 passed in 8.29s`. JUnit reports 75 tests, zero failures, zero errors, zero skips. The deciding output is retained under `LOCAL/raw/retrieval-scope-v4-fixture-review-attempt2-20261010/`: `stdout.txt` SHA-256 `5e0dde2c4b20976608ebd9f361fc44ba40dd90ce820594f0dff11a67d33ff00a`, `stderr.txt` `0ab6ef2955f256c863333dd11b269f12e73bebd9243903655025296077f51844`, `junit.xml` `8d46ed92ab0a70076b00614b0216573c15b9bcccd4ec50484b87573a24bae383`, and `exit_code.txt` `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.

An initial capture attempt also printed 75 passes but its shell wrapper failed afterward because zsh reserves the variable name `status`; that attempt is not the receipt. The clean attempt above reran the same modules with a non-reserved exit variable and is the deciding result.

The static review verdict is now supported by a fresh complete scoped consumer replay. This establishes the behavior exercised by these three modules, including the controlled FileTabular fixture and existing refusal controls; it does not establish production registry currentness, external source authority, the full composed E02 capability, or G acceptance.
