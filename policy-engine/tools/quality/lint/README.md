# tools/quality/lint

Architecture and quality gates for dependency structure, import policy, and the freeze process.

## Role in the System

- checks boundaries between `src/polisyos/*` packages;
- controls exceptions (`architecture/imports/exceptions.toml`) and debt (`import_debt_register.csv`);
- collects metrics for comparison with the CI baseline.

## Scripts

| Script                        | What It Does                                                                                                                          | Used By                                                 |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `lint_imports.py`             | Main import gate (`ARCH00x`), cycles, deep-import/legacy constraints                                                                  | pre-commit, `arch.yml`, `arch-freeze.yml` (via metrics) |
| `lint_foundry.py`             | Import and builtin ban list for `foundry` (policy: `standard/mixed/no_jax`)                                                           | `arch.yml`                                              |
| `check_scholar_imports.py`    | Prohibits the `scholar -> polisyos.fabric.io.db` dependency                                                                           | `arch.yml`                                              |
| `lint_connector_hardening.py` | P7 invariants for production connectors (`world_bank`, `eurostat`, `ukons`)                                                           | `arch-freeze.yml`                                       |
| `lint_connectors.py`          | Law A/B for `fabric/connectors` (isolation from `scientist`/`foundry`)                                                                | manual run; used in freeze metrics                      |
| `collect_arch_metrics.py`     | Collects freeze artifacts (`architecture/imports/gate_summary.json`, `architecture/imports/gate_baseline.txt`, `ruff_stats.txt`, ...) | `arch-freeze.yml`                                       |
| `compare_baseline.py`         | Compares baseline/current and checks exception policy and deep-import drift                                                           | `arch-freeze.yml`                                       |
| `lint_foundry_data_plane.py`  | P8 data-plane invariants (workflow aliases, adapter, assumptions)                                                                     | manual run                                              |
| `lint_legacy_cutover.py`      | P10 invariants for the legacy-runtime/facade cutover                                                                                  | manual run                                              |

## Inputs and Repository Connections

- `architecture/imports/policy.toml`, `architecture/imports/exceptions.toml`, `architecture/imports/exceptions.md`
- `import_debt_register.csv`
- `architecture/imports/gate_summary.json`, `architecture/imports/gate_baseline.txt`
- source code: `src/polisyos/**`
- CI configuration: `ops/ci/templates/workflows/arch.yml`,
  `ops/ci/templates/workflows/arch-freeze.yml`

## Typical Local Run

```bash
PYTHONPATH=src:. uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml
PYTHONPATH=src:. uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml --changed-only --cache-dir _cache/polisyos-tools/cache --baseline-label ci --skip-if-unchanged
PYTHONPATH=src:. uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml --fix
PYTHONPATH=src:. uv run python -m tools.quality.lint.lint_foundry --repo-root .
PYTHONPATH=src:. uv run python -m tools.quality.lint.lint_foundry --repo-root . --fix
PYTHONPATH=src:. uv run python tools/quality/lint/check_scholar_imports.py
PYTHONPATH=src:. uv run python tools/quality/lint/compare_baseline.py --current .arch-freeze/current/summary.json --mode dry-run
```

## Notes

- `compare_baseline.py` has `dry-run` and `blocking` modes.
- Exception IDs are read from Markdown table cells with the shared tokenizer; header and
  alignment rows do not become registry IDs, while an unregistered TOML exception remains a
  blocking finding in `blocking` mode.
- `lint_imports.py` includes `TYPE_CHECKING` imports only when `--allow-type-checking` is set.
- `lint_imports.py` uses a content-addressable parse cache and supports `--changed-only`; the persisted baseline hash is applied only after a successful run, so a failing state is not silently skipped in CI.
- `lint_imports.py --fix` currently performs only one safe mechanical operation: a canonical rewrite of `architecture/imports/exceptions.toml`. It does not rewrite source imports automatically.
- `lint_foundry.py` uses the registry in `tools/quality/lint/rules/`; new domain-specific rules can be added as separate modules without changing the core scanner.
- `lint_foundry.py --fix` is limited to safe autofixes. At present, it automatically removes only standalone `print()` debug calls; other findings remain report-only.
