# Tool Config Split

Source fragments for Repository Best-in-Class Phase 5.5.

- `mypy/base.ini` is the root policy surface; package debt lives in grouped override fragments and is assembled into `mypy/generated.ini` for commands that need historical suppressions.
- `ruff/base.toml` holds base rules; per-file ignores live under `ruff/per-file-ignores/` and are covered by `architecture/static_analysis_overrides.toml` owner/sunset metadata.
- `mkdocs/` keeps the site base, publication exclusions, and nav sections reviewable in small fragments; `mkdocs.yml` inherits the generated config.

Regenerate and verify with:

```bash
uv run polisyos-tools workspace tool-configs --check
uv run polisyos-tools workspace tool-configs
```
