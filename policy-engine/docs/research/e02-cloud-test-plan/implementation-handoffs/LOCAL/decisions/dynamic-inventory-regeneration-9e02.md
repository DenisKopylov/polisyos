# Dynamic import inventory regeneration (9e02)

## Result and scope

Regenerated `architecture/imports/dynamic.toml` from the repository's existing canonical collector and renderer in `tools/quality/validation/decomposition_preflight.py`. The catalog now records all 244 dynamic-import AST call sites found in the collector's selected source roots. The collector, validator, and inventory schema were not changed; `write_phase3a_artifacts` was not used. The only product-source companion is the mirrored semantic regression in `tests/repo_quality/architecture/test_decomposition_preflight_gates.py`. This note and the retained evidence are under `LOCAL/decisions`.

The gate establishes inventory agreement and validates explicit allowed targets. It does not establish approval for unresolved targets. In particular, all 154 rows with empty `allowed_targets` remain empty and review-required under the unchanged header policy. The header's `review_expires = "2026-08-04"` is expired as of 2026-10-09; it was preserved without renewal or a new authority claim.

## Complete census and reconciliation

The canonical selector walks Python files below `src`, `tools`, `apps`, and `packages`, parses each file as Python, and collects the configured dynamic-call forms through the existing `collect_dynamic_imports` implementation. The measured denominator was 3,167 selected `.py` files: 3,167 parsed, zero parse failures, 244 matched AST call nodes across 130 source files. The final classification JSON includes the per-source SHA-256 ledger for those 130 files.

Against 205 registered signatures, the current signatures reconcile as:

- 114 unchanged;
- 84 relocated (same source/call/pattern, changed line);
- 46 new;
- 7 stale.

Thus 130 current signatures were unregistered (84 relocated plus 46 new), and 91 prior signatures are absent at their exact old addresses (84 relocations plus 7 stale). The 221 pre-regeneration findings reconcile to `84 × 2 + 46 + 7 = 221`: one missing and one stale finding for each relocation, plus new and stale findings.

The seven stale rows are: `data_forge/domains/ukraine/server.py:39` and `:120` (`__import__("os")`); `foundry/calibration/dp_ci.py:20` (`__import__("pathlib")`); `foundry/plugins/discovery.py:74` (`pkg_resources.iter_entry_points`) and `:86` (`importlib.import_module`); and `runtime/quality/intervention_substrate.py:491-492` (the two GY-S3 Foundry imports). These are absent as exact source signatures in the current AST. The two GY-S3 rows are not presumed equivalent to other live calls; they are removed as stale inventory entries because their recorded calls are not present at those source addresses.

There are 90 explicit `allowed_targets`; all 90 resolve using the validator's `importlib.util.find_spec` resolution. The remaining 154 rows have empty `allowed_targets` and are reported as requiring review by the preserved policy. An early exploratory report counted literal-like `target` expressions as if they were explicit `allowed_targets`; that produced a misleading resolution tally and is not authoritative. The final report filters the actual `allowed_targets` field and is the cited classification.

## Protected metadata and final bytes

The renderer produced 244 rows, 107,988 bytes, SHA-256 `c2ebd123bd8736b82115414adbfd63650fed7e0c26ed6f6a424ab45245c19dad`, with zero validator findings. The first 1,049 header bytes remained byte-identical (SHA-256 `1761761d3cc218226bd6724e0ef7782b91b41651d1f2c5866760e113d45bcde5`). The exact preserved values are `review_owner="team-architecture"`, `reviewed_at="2026-05-06"`, `review_expires="2026-08-04"`, and the existing exception policy. The write used the canonical rendered output after the candidate validation and 130 source-hash checks; on-disk readback matched the candidate hash.

## Behavioral checks

Added `test_dynamic_imports_gate_rejects_registry_and_target_corruption` beside the existing positive gate test. It feeds the real collector's current census into the real validator, then verifies that a changed line address, a removed call row, and a nonexistent explicit allowed target each produce the corresponding rejection. The test passed after final formatting: one test, no failures/errors/skips. The existing on-disk positive test `test_dynamic_imports_gate_resolves_registered_targets` also passed against the regenerated inventory.

Commands and retained outputs:

- `PYTHONPATH=src:. .venv/bin/python -m pytest --tb=short -rA --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/raw/dynamic-catalog-corruption-final.xml tests/repo_quality/architecture/test_decomposition_preflight_gates.py::test_dynamic_imports_gate_rejects_registry_and_target_corruption` — output: `raw/dynamic-catalog-corruption-final.log` (SHA-256 `49737a997dcf76a638c7713752193c113c81a70aeb8b75befed37ef1df72107f`); JUnit: `raw/dynamic-catalog-corruption-final.xml` (SHA-256 `dc7c5fb4561bcc4e2835ca073a1c60f0008651cb9d78f6b6f5565c5a34d87fac`).
- Existing positive selector `test_dynamic_imports_gate_resolves_registered_targets` — output: `raw/dynamic-catalog-on-disk-gate.log` (SHA-256 `d96285c1a2caae5ba7d4c2bceccb46c913e58b9670c465f257b561c3b4a54e7d`).
- `.venv/bin/python -m ruff check tests/repo_quality/architecture/test_decomposition_preflight_gates.py` and `.venv/bin/python -m ruff format --check tests/repo_quality/architecture/test_decomposition_preflight_gates.py` — both passed; outputs are `raw/dynamic-test-ruff-final.log` and `raw/dynamic-test-format-final.log`.

The full pre-regeneration findings, final per-file classification/source-hash ledger, canonical render validation, write/readback metadata, and complete gate outputs are retained in `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/raw/`. The final census classification is `dynamic-census-classification-final.json` (SHA-256 `642fd6afe0c9b39c289fd84c3747a50823106b839bcdf76de7d20a72aa937f64`); the pre-write complete findings are `dynamic-catalog-before.log` (SHA-256 `b95c8719a3ad6fe25d71a78a9c2d5920f0b90a644d4fd0af8eb6da61a4064f1b`). The final catalog and mirrored test have SHA-256 values `c2ebd123bd8736b82115414adbfd63650fed7e0c26ed6f6a424ab45245c19dad` and `05c936a2f5b858a7ac0ba5295bdecbe87a28ea31bfd9b4d887357fd07818f602`.

## Pattern pass

This closes the inventory-drift class by regenerating the complete collector-derived set, rather than patching a sample of missing entries (P35/P40). The semantic controls exercise the validator's actual source of truth and fail on property corruption, not merely on marker drift (P29). Remaining empty-target rows are explicit review debt, not treated as green authority. The acceptance signal is: all selected files parse, the canonical complete inventory yields no findings, target corruption and missing/relocated entries are rejected, and protected review metadata is unchanged.
