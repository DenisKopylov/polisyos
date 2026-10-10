# Independent public-surface and consumer review

Review target: candidate worktree `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`, with parent-supplied source base `077a572ff5880b3f50a85d3e3db6a232d277659a`. The immutable candidate commit was not available during this pass, so the review is bound to the per-file SHA-256 values in [public-surface-runtime.txt](raw/public-surface-runtime.txt) (raw log SHA-256: `783ae9bf0d3e25d2aec188537962c51a6d8a7f9c80c8789af26a4aab7dd43728`). I used each worktree's own `.venv/bin/python` with `PYTHONPATH=src:.` and one numerical thread. No product files, generators, browser servers, tests, or Git commands were run; only this report and its raw log were written.

## Export resolution and compatibility

I walked the full declared export sets (`__all__`, or Catalog's `_EXPORTS`) in the six requested Python facade modules, once in the candidate and once in pinned G. Counts below are scoped to these six module files, not a repository-wide public API census.

| Facade | G declared / resolved | Candidate declared / resolved | G-resolved names missing in candidate | Candidate additions resolving |
| --- | ---: | ---: | ---: | ---: |
| `polisyos.common.migrations` | 3 / 3 | 5 / 5 | 0 | 2 |
| `polisyos.core.artifacts` | 54 / 54 | 66 / 66 | 0 | 12 |
| `polisyos.core.contracts` | 489 / 475 | 642 / 642 | 0 | 167 |
| `polisyos.foundry.execute` | 3 / 3 | 4 / 4 | 0 | 1 |
| `polisyos.data_requirement` | 11 / 11 | 11 / 11 | 0 | 0 |
| `polisyos.data_forge.read_api.catalog` | 131 / 131 | 136 / 136 | 0 | 5 |

For all overlapping resolvable names, the defining module and qualified name stayed the same. The candidate additions resolve to their existing owners: Common migration traversal types/functions; Core manifest-profile, authority-envelope, durability and IR-adapter facade exports; the Foundry snapshot-layout exception alias; and Catalog's response envelope and shared embedding-generation read helpers. The Catalog additions are `DatasetSearchResponse`, `EmbeddingGenerationRef`, `embedding_generation_matches_encoder`, `generation_basis_matches_members`, and `resolve_embedding_generation`. The 12 Core artifact names and their origins are recorded in the raw log.

G's Core contracts facade has one literal `*_CHRONOLOGY_EXPORTS` entry and 13 other entries in `__all__` that do not resolve; its wildcard import fails on the literal. The candidate resolves all 642 actual `__all__` entries, and a real `from polisyos.core.contracts import *` imports all 642 with `NativeChronologyQualified` retaining its defining class object. The repository has the matching generic test at `tests/unit/core/contracts/test_ir_ref_facades.py::test_core_contract_wildcard_import_resolves_the_declared_surface`. I do **not** classify G's failure as “inherited” under P41: this was an ABI comparison against G, not an exact slice-base replay with a complete changed-import denominator.

`data_requirement.__all__` is unchanged. Three extra names now resolve through its lazy `__getattr__` but are outside `__all__`: `PolicyGrammarIntent`, `PolicyGrammarConceptSpineRefs`, and `UniversalAuthorityProfile`. The architecture public-surface contract does not list `polisyos.data_requirement`; treat these direct aliases as internal until that owner classifies the package. Common's root `__all__` exposes `migrations`, Core's root exposes `artifacts`, and Data Forge's `read_api` root exposes `catalog`; those actual parent-facade re-exports resolve in the candidate.

## Legal and Catalog consumers

The Legal chain reaches the first-party page. `GET /api/v1/control/lex/search-profile` returns an immutable, extra-forbid profile derived from the selected fact-generation selector and inventory. The page refetches that profile at search time and only sends `query_generation_intent` when its status is available and its `output_dir` equals the currently selected directory. It renders `search_mode` and the nullable refusal even when there are no result rows. The browser journey in `apps/runtime-dashboard/e2e/journeys/catalog-profile-source-bound.spec.ts` checks the selected intent on the request, the vector-compatible response, and stale intent degrading to text while preserving the returned Legal fact. The page unit cases cover request binding and the visible refusal. I reviewed source and tests but did not execute the browser journey here.

The cross-boundary DTOs are strict: `LegalQueryGenerationIntentV1` is frozen with `extra="forbid"`; `LexSearchRequest`, `LexSearchResponse`, `DatasetSearchResult`, and `DatasetSearchResponse` reject extra fields. Catalog's response envelope is frozen and validates that vector mode carries no refusal, text fallback carries a refusal, and unavailable query status carries a limitation. Its graph returns rows and status from the same locked invocation. The registered `search_datasets` tool adapter selects `search_datasets_with_status`, so its response retains an empty-result refusal rather than reconstructing status from last-query metrics. The existing falsifier is `test_registered_search_tool_keeps_refusal_for_empty_query_results`; the runtime-quality semantic projection and Catalog benchmark both persist per-query status from the envelope.

The documented legacy direct-list methods remain list-shaped and cannot carry query-wide status if there are no rows. That limitation is explicit; callers requiring status use `search_datasets_with_status`, and the registered tool now does. The older row-list context formatter also has no place to carry empty-query status. This is the same P40 class as the earlier downstream status-loss finding, now closed across the canonical tool and benchmark projections with a query-wide envelope. The bounded residual is the compatibility list API. Its falsifier is the zero-hit text-fallback query through the registered tool: removing the adapter's status-method selection must make the empty-response test fail. I found no second escape in the named registered-tool, benchmark, or workspace projection paths.

For P38, `search_mode="vector"` means a vector-enabled hybrid path; it does not mean vector-only ranking. The Catalog README says so, and the UI's “Vector retrieval” label should be read that way. Legal's known asset-versus-executable identity gap remains explicit in its release fragment: changing executable `encode` behavior while retaining the same weights/config/tokenizer is not detected. The HTTP positive case is a compatibility witness, not a production authority, model-provenance, or semantic-quality claim.

## Inventory and release metadata

The current inventory explicitly leaves several dynamic facades unresolved: `export_count=null`, `known_export_count=0`, `complete=false`, with `exports_scope` stating that zero known names is **not** an empty runtime namespace. The candidate-scope text also says those names are not proven. I therefore make no zero-export claim. The runtime imports above are the property check for the selected six facades; the static inventory remains a bounded source-reader view. In particular, the inventory's Core-contracts source hash matches the candidate source but its parser does not expand the starred chronology tuple. The runtime namespace test is the falsifier for a missing declared symbol.

The public-surface policy in `architecture/public_surface/contract.toml` requires `public_surface_inventory_reviewed=true` once the inventory is regenerated or reviewed. The reviewed feature fragments still have these pending values:

- `2026-10-09-e02-routine-public-boundaries.toml`: false.
- `2026-10-09-e02-authority-envelope-selected-view.toml`: false.
- `2026-10-09-e02-c12-catalog-search-status.toml`: false on both the main fragment and its compatibility entry.
- `2026-10-09-legal-generation-intent-consumer.toml`: false; the API regeneration requirement is also covered by `2026-10-09-e02-composed-api-artifact-consumers.toml`, whose flag is false.
- `2026-10-09-e02-shared-embedding-identity.toml`: classifies Legal/Catalog read-facade exports as public-experimental but has no review flag.
- The earlier `2026-10-07-e02-b53-producer-publication-reconciliation.toml` is false at top level and carries the public-experimental durability facade compatibility entry.

Root reports that the OpenAPI/client/dashboard/inventory regeneration pass succeeded. After the reviewed inventory is committed, set the applicable flags true and add the missing shared-identity flag. `2026-10-09-e02-can-options-mapping.toml` is classified internal and does not need a public-surface flag. The Legal capability fragment's internal classification describes its producer/admission core; the separate composed API fragment must continue to carry the public request/response and regenerated-client change.

**P40 classification:** SAME class, at the public-surface/consumer boundary. The typed Catalog envelope widens the mechanism across the registered tool and downstream benchmark/report path; the documented list-only compatibility edge remains bounded as above. **P41 classification:** not established for G's old Core-contracts runtime failure; this report makes no inherited-debt attribution.

