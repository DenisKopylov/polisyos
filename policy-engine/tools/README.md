# Tools

`tools/` is the canonical executable surface for `policy-engine`.

Public rule:
- use `polisyos-tools <category> <command>` for human and CI entry points;
- keep top-level `tools/<category>` imports as compatibility packages;
- treat `scripts/` and root `benchmarks/*` executables as deprecated wrappers during the migration window.

## Zones

Internal implementation code now lives under zoned packages:

| Zone | Categories | Purpose |
|---|---|---|
| `devx` | `workspace`, `architecture`, `connectors`, `foundry` | contributor setup, scaffolding, repo structure, codegen |
| `quality` | `lint`, `diagnostics`, `validation`, `testing`, `ci` | quality gates, diagnostics, validation, mutation/integration checks |
| `ops` | `cloud`, `release`, `migrations`, `runtime`, `data`, `ukraine_data`, `calibration` | operational tasks, runtime/release, data prep, migration and cloud workflows |
| `research` | `benchmarks`, `demos` | benchmark orchestration and manual research/demo surfaces |

Canonical implementation layout:

```text
tools/devx/<category>/
tools/quality/<category>/
tools/ops/<category>/
tools/research/<category>/
```

Compatibility layout retained for one deprecation window:

```text
tools/<category>/...
```

Those top-level packages are thin shims and documentation anchors. New tool code
must be added only under the zoned implementation path.

## How To Add A Tool

1. Choose the zone.
2. Choose the category.
3. Add the module under `tools/<zone>/<category>/`.
4. Register the category in `tools.registry` if it is new.
5. Expose the command through `main(argv: Sequence[str] | None = None) -> int`.

Do not create a new top-level `tools/<category>` package unless it is part of
the zone manifest and the compatibility layer.

## Benchmark Boundary

- `tools/benchmarks` is the public executable surface for benchmarks.
- `tools/research/benchmarks` contains the canonical benchmark orchestration implementation.
- root `benchmarks/` is the benchmark-domain package:
  suites, fixtures, comparators, support/runtime/reporting code.
- root `benchmarks/*.py` and `benchmarks/*.sh` executables are compatibility wrappers only.

## Scripts Policy

- `scripts/` is no longer a place for new tool logic.
- surviving script paths are explicit deprecation wrappers that print a replacement command.
- wrappers stay only while workflows, docs, or external operator muscle memory still depend on them.
- once a wrapper has zero references in workflows/docs/tests/generated reference, it can be removed.

## Common Commands

```bash
uv run polisyos-tools --help
uv run polisyos-tools list
uv run polisyos-tools list --by-zone
uv run polisyos-tools graph --format mermaid
uv run polisyos-tools docs --output docs/reference/tools.md
```

## Reference

- [tools/benchmarks/README.md](./benchmarks/README.md)
- [tools/workspace/README.md](./workspace/README.md)
- [tools/cloud/README.md](./cloud/README.md)
- [docs/reference/tools.md](../docs/reference/tools.md)
