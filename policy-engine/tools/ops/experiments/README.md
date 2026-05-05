# Ops Experiments Tools

Operational experiment runners live here and are exposed through the unique CLI
category `ops-experiments`:

```bash
uv run polisyos-tools ops-experiments --help
```

This keeps the physical Phase 1D layout at `tools/ops/experiments/` while
avoiding a duplicate public category name with `tools/research/experiments/`.
Use this package for experiment suites that execute operational scenarios,
deadline runs, or campaign-style validation passes.
