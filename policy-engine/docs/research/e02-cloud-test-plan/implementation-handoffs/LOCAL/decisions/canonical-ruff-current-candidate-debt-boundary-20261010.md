# Canonical Ruff findings and candidate boundary — 2026-10-10

The captured canonical Ruff command exits 1 with **2,027 findings**. The complete stream parses into 2,027 primary-location rows with code totals identical to the run summary, all source paths present at readback, and current content hashes for every diagnostic file. It is a real repository-wide lint failure; the current candidate’s focused Ruff pass does not make the canonical gate green.

The deciding receipt is `raw/pre-freeze-canonical-ruff-check-20261010/command.json@e19c2666ca85447c19bf72931cd42360c7a2ab0e6d2a2b6bd2c28db5f776f817`, with full stdout `stdout.txt@704f55a9b18f5431b93aa3ddb4a0b3787b0e47d61a92e9c19f715ba8c158482f` (1,286,441 bytes), empty stderr, and exit 1 at HEAD `f52809e8210714131f53c7b90bd53a9215c69d69`. The command was run from the product root with this exact argv:

```text
.venv/bin/python -B -m ruff check --extend-exclude benchmarks --extend-exclude tools/research/benchmarks --extend-exclude tools/research/demos --extend-exclude tools/research src/polisyos tests tools schemas examples ops/cloud/gcp/upload_gonka_secrets.py jax_bootstrap.py migrate.py
```

At capture, the Ruff config chain was `ruff.toml@8887d0a15457d44ebb1a5b5aee8110dd5101dc9e952649cd0490b845af2d933e` and `ruff.generated.toml@51dd7d4fb4937537d815e7b791541c9f09b0b9f413ec06e6c69b221c0096d64f`; the effective-scope owner files were `_repo_hygiene.py@7ed1b535f3a253e3cc53edf37429cac9a47ccd22742c7b3fa78ed0f748c65cb4` and `lint_fast.py@8a347c43d7f0a9a06a5fadd660b9197b0a5a67abf42b1e0bff7b6a7b6a87b061`. This is the canonical authored-scope command, not the separate exploratory `ruff check .` run, whose denominator included local recovery scripts and legacy tooling.

The full diagnostic classification and source-hash manifest are in `raw/pre-freeze-canonical-ruff-check-20261010/canonical-ruff-classified-diagnostics.json@d10452030a3479ff77de3dd068e4101a6487f31a0920f44576d4352b32bd8831`. It contains one record per finding with code, message, path, line, column, and current source SHA-256; the sorted 765-file path/hash manifest digest is `d6fdd4f919c00e0c611b2cee81eeb132de8ff412c87a856b88edfc7999b55fb7`. Hashes are readback hashes for the current worktree, not hashes captured during the original Ruff execution; that receipt recorded config hashes but no complete per-input source manifest. The reproducer/parser is `classify_canonical_ruff.py@34e0e9f04ddae7c3278abf4942ee92ebb80ae51e5ffed911b2c6f271af18bfb7`.

The recomputed primary-location set has **765 distinct paths**. The prior derived `parsed-complete-diagnostics.json` reports 763; its code totals still match, but its path cardinality does not. The new parser checks all 2,027 rows against the complete prior code histogram and finds no missing files or parse errors, so this note uses 765 and preserves the discrepancy rather than silently inheriting the smaller number. The 765 diagnostic paths are not the Ruff input denominator: the command scans the named source/test/tool/schema/example roots, including files with no findings.

| Ruff code | Findings | Classification |
|---|---:|---|
| I001 | 682 | Import-block order/formatting across 659 current files |
| F821 | 448 | Undefined names requiring static-binding review; most arise at dynamic split-module boundaries |
| Other codes | 897 | Captured row-by-row as `other-canonical-lint-unadjudicated`; not adjudicated by this bounded review |

## F821: real static-binding debt at dynamic boundaries

| Current diagnostic file | Rows | Current source SHA-256 | Source finding |
|---|---:|---|---|
| `src/polisyos/foundry/methods/catalog/causal/causal_engine/discovery.py` | 205 | `3d365c4629ea0a8069f9b6da28d83a677fc6895d726d8a52e84f1803b5f3620b` | `globals().update(...)` imports the artifacts namespace at module load; the neighboring `identification.py` has a `TYPE_CHECKING` import declaration for the same split boundary. Of the 63 unique reported names, 60 are current top-level bindings in artifacts/API; the other 3 (`identified`, `non_identified`, `oracle_needed`) are quoted values inside `Literal[...]` annotations (8 diagnostics), not runtime symbols. Declare `Literal` and the owner bindings statically; do not add string values as globals. |
| `src/polisyos/foundry/methods/catalog/causal/causal_engine/sensitivity.py` | 104 | `4ed148c93c820f26833c073d116902fb4f6ac73f0681a88c17561ed1b75c76d9` | Same dynamic artifact-global import; all 17 unique reported names are present in the artifact module’s current top-level bindings. Mirror the `identification.py` `TYPE_CHECKING` owner imports. |
| `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_api.py` | 88 | `1459cd2f0b8b932408d2c3b33964dfccf9afa00ab899101fb5e523ab4b2efc48` | The public `resolve_extract.py` facade synchronizes its globals into four implementation modules before delegation (`_sync_implementation_globals`, lines 51–59, and delegate calls at 65–75). All 44 unique reported names are current top-level bindings across the four implementation modules. |
| `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py` | 29 | `a177d4fa97322f1f75876113708a9b441c3566d3d0688c6d4eae562b707728c4` | Same facade synchronization; all 12 unique names exist in those implementation modules. Together the two files have 117 findings over 56 unique owner symbols. |
| `src/polisyos/foundry/methods/catalog/causal/interference/api.py` | 12 | `4d322ffafcddbb41a20150f868e7f6f6b1e2a7b230b79b18ea81d994771d411e` | `globals().update(...)` imports from `identification` and `estimation` (lines 91–92); all 6 unique names are current top-level bindings there. Add static `TYPE_CHECKING` declarations while preserving runtime exports. |
| `src/polisyos/data_forge/domains/catalog/batch/core_sources/transformers.py` | 6 | `303ffe1af3c52258dbe448bb115a08475ecc646bd7da78a7dea6f2f39bc6af60` | Three lazy owner-bound proxies resolve `_infer_ilo_dimension_order` and `_normalize_dimension_order` from `writers`, and `_records_from_payload` from `loaders` (`__resolve_implementation_dependency`, lines 209–234). All three owners currently define those names. Declare the owner relationship statically rather than suppressing F821. |
| `src/polisyos/foundry/methods/catalog/causal/causal_engine/api.py` | 3 | `0bddffae20759e3ba21365d3b26aea2e589a944c22cebb2225285b4b12ef9450` | Two actual annotation imports are missing: `Any` and `ArtifactStore`. Add their direct imports. |
| `src/polisyos/scientist/methods/search/adapters.py` | 1 | `7cba0380ad7d4b2c040f63e7487f15faa952136edb19bdd4ed56fd895442e068` | One actual annotation import is missing: `Any`. |
| **Total** | **448** |  | **436 owner/global references, 8 quoted `Literal`-value reports, and 4 direct missing-import reports.** |

The source-based repair is narrow: declare dynamic sibling dependencies under `TYPE_CHECKING` (the causal `identification.py` pattern already demonstrates this), keep compatibility exports and runtime routing intact, and directly import the three missing annotation names. Validate the facade through its public entrypoint and a consumer of each split mixin/proxy; avoid adding noqa exceptions or changing selectors. The recorded command says 973 findings are autofixable (64 only with unsafe fixes), but that is not authority to apply a broad repository-wide rewrite.

## I001: 682 import-order findings across 659 files

| Current path group | Findings |
|---|---:|
| `tests/unit` | 542 |
| `src/polisyos/scientist` | 41 |
| `src/polisyos/fabric` | 20 |
| `src/polisyos/ir` | 8 |
| `src/polisyos/foundry` | 7 |
| `src/polisyos/data_forge` | 4 |
| `src/polisyos/core` | 2 |
| `src/polisyos/runtime` | 2 |
| `tests/property` | 15 |
| `tests/contract` | 7 |
| `tests/integration` | 5 |
| `tests/_helpers` | 3 |
| `tests/repo_quality` | 3 |
| `tests/performance` | 2 |
| `tools/ops_runners` | 7 |
| `tools/ci` | 6 |
| `tools/quality` | 6 |
| `tools/archive` | 2 |
| **Total** | **682** |

These are source import-block findings, not the earlier config-caller defect: the canonical command is product-rooted and uses the generated config binding. They remain repository-wide debt. Repair them in reviewed scoped batches, preserving intentional import side effects and local imports; do not restore a broad `ruff check .` scope, expand exclusions, or run an unreviewed `--fix` across the repository.

## Candidate boundary and gate provenance

The candidate’s focused Ruff check is reported passing. The diagnostic-location intersection with its changed paths was reported empty, but that is not the full input intersection. The canonical argv scans `src/polisyos`, `tests`, and `tools`, which contain candidate source and test inputs; the capture has no expanded input-file hash manifest. Thus zero diagnostic-path overlap does not prove source-input disjointness. Under P35/P38/P41, the gate remains **red and not inherited**: the path-count/diagnostic set is recomputed from the complete stdout, while whole-input disjointness is not established by this receipt and the full input set intersects the candidate. Do not carry this red as inherited, and do not claim the repository gate is green from the focused candidate pass.

Relevant failure/repair patterns: P35 (full-set enumeration), P37 (identify the gate predicate’s provenance), P38 (diagnostic paths are not input disjointness), and P41 (slice-base, complete-input intersection required for inheritance). No code, config, exception, expiry, or waiver changes were made here; no Ruff command was rerun and no automatic fixes were applied.
