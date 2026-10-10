# Canonical Ruff current residual

The scoped canonical Ruff command is red at `c9d0941864a8`: 2,029 diagnostics across 767 reported paths and 55 rule codes. It traversed 6,136 effective Python files. The full JSON output and complete by-code/by-file classification are retained in ignored raw receipts below.

The deciding command ran from `policy-engine/` with Ruff `ruff 0.14.10`:

```text
.venv/bin/python -m ruff check --output-format json \
  --extend-exclude benchmarks \
  --extend-exclude tools/research/benchmarks \
  --extend-exclude tools/research/demos \
  --extend-exclude tools/research \
  src/polisyos tests tools schemas scripts examples \
  gcp/upload_gonka_secrets.py ops/cloud/gcp/upload_gonka_secrets.py \
  jax_bootstrap.py migrate.py
```

The largest rule counts are `I001` 682, `F821` 448, `F401` 260, `E501` 217, `RUF001` 98, `S110` 96, `ANN401` 45, `TC003` 15. The largest file counts are `src/polisyos/foundry/methods/catalog/causal/causal_engine/discovery.py` 213; `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_api.py` 171; `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py` 116; `src/polisyos/foundry/methods/catalog/causal/causal_engine/sensitivity.py` 104; `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_providers.py` 100; `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_io.py` 97. Two `E902` entries come from the explicit input arguments `gcp/upload_gonka_secrets.py` and `scripts`; those paths are absent in the base tree as well as the current checkout. The scope declarations are in `tools/devx/workspace/_repo_hygiene.py:18` and `:20`; the file has the same blob at base and head, and both paths are absent from both trees.

Between exact base `93d6aa62a8d236667fdf322a5fc17962523b185e` and head `c9d0941864a801e3f143b5cc2e94ec1c26f72e22`, 890 changed Python paths are in the declared source scope; 886 appear in Ruff’s effective 6,136-Python-file manifest. The four excluded paths are `tests/unit/benchmarks/symbolic/test_helpers.py, tools/research/benchmarks/jax/bench_simulation.py, tools/research/demos/run_laffer_demo.py, tools/research/demos/run_mechanism_design.py`. None of the 886 changed effective Python paths has a diagnostic. This is a path-level result, not an inherited-green result: the effective input intersection is nonzero, and the active Ruff configuration changed.

The six changed Ruff configuration paths are recorded in the classification JSON. The active product-root chain moved from `ruff.toml -> architecture/tooling/ruff/generated.toml` to `ruff.toml -> ruff.generated.toml`. After normalizing config-relative glob prefixes, lint rule selection, ignores, confusables, and per-file ignore entries match except for removal of `src/polisyos/calibration/**`. The current output has zero diagnostics under `src/polisyos/calibration/`, so that removal does not explain this run’s failures. The current root config also adds `src = [".", "src"]`; this can affect import sorting and makes the 682 `I001` findings config-sensitive. No base Ruff replay was made, so the I001 introduction question remains `not_established`. The new `workspace_root.toml` fragment is not loaded by this product-root command.

There are no directly attributable changed-source Ruff findings. The whole result is `not_established` for P41 inheritance because 886 changed files intersect the actual input set and the active config changed. Do not report the global gate as inherited or green. This work identifies no E02 source-format/type diagnostic in a changed file. The two nonexistent input paths are a narrow, same-class command-scope defect: make the declared scope resolve existing paths as one rule, or carry both as a bounded residual until that owner decides the intended path. The remaining unchanged-file diagnostics cannot be attributed to the E02 range without relying on a proxy or an unperformed config replay.

P40 classification: **same canonical-Ruff red class, one level deeper**. The expanded effective-file denominator is 6,136 Python files, not only the edited paths. The paired E902s widen one scope-resolution issue; they should be handled by a general scope-path invariant rather than separate one-path patches. The falsifier was run: the exact effective file manifest shows a nonzero changed-path intersection and zero changed-path diagnostics, disproving both “the full result is disjoint” and “changed source files account for the current findings.”

Evidence:

- Full diagnostics: `LOCAL/raw/canonical-ruff-current-residual-20261010/ruff.json` (SHA-256 `00fc7dedfea0a08db5fbadc5e6cfd01c5b334256d9f39007c01a26d94acbf34b`).
- Effective Ruff file manifest: `LOCAL/raw/canonical-ruff-current-residual-20261010/effective-files.txt` (SHA-256 `8d1cc03ea5357bb993aefba0cc50ce57b2866790ea9b34435758cf1209e9f1d4`).
- Complete by-code/by-file/by-file-code counts and Git intersection: `LOCAL/raw/canonical-ruff-current-residual-20261010/ruff-classification.json` (SHA-256 `8fef86aeab11c28e9f82aae5621183be56ee02f61f8078ccd02ae937467b8ee0`).

## Follow-up: shared authored-scope repair at `b45383cec354`

The preceding section records the pre-repair `c9d094` snapshot. At `b45383cec354a76fbb6bfb721f7a75e952bfa324`, the shared `AUTHORED_PYTHON_FORMAT_SCOPE` still named two paths absent from the product tree: `scripts` and `gcp/upload_gonka_secrets.py`. The relocated `ops/cloud/gcp/upload_gonka_secrets.py` is a real file and remains selected; the broader `tools` scope also remains. `format_check.py` and `lint_fast.py` consume the shared tuple (or its derived lint tuple), so the repair removes both stale entries once in `_repo_hygiene.py`. The test and companion search found no test pinning those entries; existing scope-sequence tests derive the command from the tuple. Historical receipts were preserved.

The canonical JSON lint command was rerun at the same HEAD before and after the tuple change. It fell from 2,029 to 2,027 diagnostics; `E902` fell by exactly two and every other rule count stayed the same. The effective manifest remained byte-identical at 6,143 paths, including 6,136 Python files (SHA-256 `8d1cc03ea5357bb993aefba0cc50ce57b2866790ea9b34435758cf1209e9f1d4`). The shared tuple now has no missing paths. `_repo_hygiene.py` is SHA-256 `7ed1b535f3a253e3cc53edf37429cac9a47ccd22742c7b3fa78ed0f748c65cb4`; its diff deletes only those two tuple entries.

The full format consumer also ran with the repaired tuple and reported no input-path errors. It remains red because 1,571 files would be reformatted and 4,758 are already formatted; that broader formatter debt is outside this repair. `ruff format --check tools/devx/workspace/_repo_hygiene.py` passes. The whole lint gate also remains red at 2,027 diagnostics, so this does not claim repository-wide lint closure.

P40 bucket: **same stale authored-scope path class, widened across the shared lint/format tuple**. Both sibling path failures are removed in one source owner and falsified through the real Ruff command, with the effective file manifest unchanged. This closes the current two-path instance without changing unrelated formatting or lint findings.

Follow-up receipts are in `LOCAL/raw/canonical-ruff-scope-repair-20261010/`: `before.json` SHA-256 `00fc7dedfea0a08db5fbadc5e6cfd01c5b334256d9f39007c01a26d94acbf34b`, `after.json` SHA-256 `164c3876c0a4e3336d2be98dc4821625abe87b8ecbbafefaa13e301235544344`, `after-effective-files.txt` with the unchanged manifest hash above, and `receipt.json` SHA-256 `bb1e0f037631b9f29b1f0e6c182600828acc6886bacefd66510387ba793ea1d8`. The complete format output is retained as `format-after.txt`.
