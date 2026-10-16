# Tool Config Split

Source fragments for Repository Best-in-Class Phase 5.5.

- `mypy/base.ini` is the root policy surface; package debt lives in grouped override fragments and is assembled into `mypy/generated.ini` for commands that need historical suppressions.
- `ruff/base.toml` holds base rules; shared per-file ignores live under `ruff/per-file-ignores/` and are covered by `architecture/tooling/static_analysis_overrides.toml` owner/sunset metadata. The workspace-root config follows Ruff discovery precedence for nested `pyproject.toml`, `ruff.toml`, and `.ruff.toml` files. It projects per-file-ignore maps only from direct product-root extensions with literal selected-config path components and positive relative matchers made from literal segments, `*`, or complete-component `**`. It fails closed on path glob metacharacters, backslashes, negative or otherwise unrepresentable matchers, malformed maps, unsupported local/indirect maps, or overlapping override scopes. Other nested Ruff settings remain local and are not projected into the single workspace-root config.
- `mkdocs/` keeps the site base, publication exclusions, and nav sections reviewable in small fragments; `mkdocs.yml` inherits the generated config.

Regenerate and verify with:

```bash
uv run polisyos-tools workspace tool-configs --check
uv run polisyos-tools workspace tool-configs
```

## Package build configuration

The native `hatch.toml` owns wheel packages, build output directory, and sdist
inclusions. `pyproject.toml` retains build-system requirements and all project
metadata, dependencies/extras, scripts, extension groups, and uv project inputs.
Copy both files into every packaging context; copying pyproject alone lets
Hatchling fall back to different package selection and output defaults.

The focused migration tests build the real declared packages using the backend,
compare every wheel member except RECORD (including metadata and entry points),
compare sdist contents, rebuild from sdist, and exercise missing/wrong config.
The isolated runtime/build context excludes ignored files and the restricted
`DEBT-REGISTER.md` and `LEDGER.md` documents; their contents are never copied or
read by these tests. Test output discloses the excluded basenames. Every other
enumerated source member must be a readable regular file: a missing or non-file
member fails context preparation instead of silently shrinking the denominator.
Docker COPY checks cover packaging inputs, not complete container health.

Build-only test dependencies must be present in the selected interpreter. With
Hatchling 1.27.0 and `build` installed, run without syncing the environment:

```sh
uv run --no-sync python -m pytest -o addopts='' tests/repo_quality/tools/test_hatch_packaging.py -q -s
```

A build-config relocation still changes pyproject bytes. Root must reissue the
live dependency-profile and authority rows through the existing
`foundry sync-dependency-profile regenerate-owner` command, check them, and run
the corrupt-field drift check. Historical frozen evidence retains its original
identity. The physical 300-line gate measures size, not configuration complexity.

## PyArrow stubs for strict typing

The `lint` optional dependency pins `pyarrow-stubs==20.0.0.20260819` for strict Mypy checks of
the runtime quality compiler. This third-party stub release declares `pyarrow>=20`; the current
lock selects PyArrow 22.0.0, so it meets the published lower bound. This is bounded evidence for
the repository's exercised PyArrow calls, not a claim of full PyArrow 22 API parity. The stub
project publishes a 20-series and does not state PyArrow 22 / Python 3.14 conformance. The pinned
wheel SHA-256 is `297e60b6e5314739c082b4757d090d8be6047465510eb0684ca954ef7ea58be3`. The local
research receipt retains the metadata and call-surface probes.

For a fresh contributor environment, run the baseline recipe from `policy-engine/`:

```sh
uv sync --frozen --extra lint --extra test --extra runtime
```

For an existing E02 environment, preserve its complete selected extras and backend recipe;
`--frozen` fixes the lock but an exact `uv sync` removes unselected dependencies. An environment
that uses `ml` must retain that extra as well. To add only this locked stub wheel to an existing
environment, verify its SHA-256 above and use the already downloaded local wheel:

```sh
uv pip install --offline --python .venv/bin/python --no-deps /absolute/path/to/pyarrow_stubs-20.0.0.20260819-py3-none-any.whl
.venv/bin/python -m tools.devx.workspace.core_runtime_mypy \
  src/polisyos/runtime/quality/capability_index_compiler.py
```

This narrow installation preserves the existing runtime and backend distributions.
The Core Runtime helper uses the generated project MyPy policy and checks each file separately.

The dependency is development tooling only. It does not change PyArrow's runtime import path,
Parquet serialization behavior, or any scientific/runtime contract.
