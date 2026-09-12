# Tool Config Split

Source fragments for Repository Best-in-Class Phase 5.5.

- `mypy/base.ini` is the root policy surface; package debt lives in grouped override fragments and is assembled into `mypy/generated.ini` for commands that need historical suppressions.
- `ruff/base.toml` holds base rules; per-file ignores live under `ruff/per-file-ignores/` and are covered by `architecture/tooling/static_analysis_overrides.toml` owner/sunset metadata.
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
