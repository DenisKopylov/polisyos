# Tools (`tools/`)

## Purpose

`tools/` — каноническая исполняемая поверхность `policy-engine`: единый CLI
`polisyos-tools`, зональная раскладка implementation-кода и совместимые
wrapper-пути для migration window.

## Where to Start

- CLI boundary: `pyproject.toml` (`[project.scripts] polisyos-tools = "tools.cli:main"`).
- Command router: `tools/cli.py`.
- Tool metadata, aliases, dependency graph и docs generation: `tools/registry.py`.
- Canonical implementation roots:
  `tools/devx/`, `tools/quality/`, `tools/ops/`, `tools/research/`.

## Public Entrypoints

| Entrypoint | Contract |
| --- | --- |
| `uv run polisyos-tools <category> <command>` | Основной human/CI entrypoint для всех инструментов. |
| `python -m tools.cli` | Низкоуровневый CLI boundary для debugging и embedding. |
| `tools/<category>/...` | Compatibility packages; новые implementation-модули сюда не добавляются. |
| `docs/reference/tools.md` | Generated reference для публичного command catalog. |

## Depends On / Depended On By

- **Depends on:** `tools._lib/*`, zoned category packages, `pyproject.toml`,
  `uv`, и registry metadata в `tools/registry.py`.
- **Depended on by:** contributor workflows, локальные quality gates,
  `.github/workflows/*`, generated tool reference, onboarding и release/ops
  automation.

## Zones

| Zone | Categories | Purpose |
| --- | --- | --- |
| `devx` | `workspace`, `architecture`, `connectors`, `foundry` | contributor setup, scaffolding, repo structure, codegen |
| `quality` | `lint`, `diagnostics`, `validation`, `testing`, `ci` | quality gates, diagnostics, validation, mutation/integration checks |
| `ops` | `cloud`, `release`, `migrations`, `runtime`, `data`, `ukraine_data`, `calibration` | runtime/release/data/cloud operational flows |
| `research` | `benchmarks`, `demos` | benchmark orchestration и manual demo surfaces |

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

## Common Commands

Команды ниже smoke-tested на `2026-04-17`, если явно не помечены как
`conceptual`.

| Command | Purpose | Status |
| --- | --- | --- |
| `uv run polisyos-tools --help` | Показать root CLI и глобальные опции. | `smoke-tested` |
| `uv run polisyos-tools list --by-zone` | Просмотреть публичный command catalog по zoned layout. | `smoke-tested` |
| `uv run polisyos-tools graph --format mermaid` | Сгенерировать dependency graph инструментов в Mermaid. | `smoke-tested` |
| `uv run polisyos-tools docs --output docs/reference/tools.md` | Пересобрать generated tool reference. | `smoke-tested` |
| `uv run polisyos-tools workspace ci-parity --skip-browser` | Прогнать локальный CI-like pass, включая docs checks по умолчанию. | `conceptual` (тяжёлый агрегирующий gate) |

## Test And Verification

| Command | What it verifies | Status |
| --- | --- | --- |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .` | Документация и generated references не расходятся с repo reality. | `smoke-tested` |
| `uv run pytest -q tests/tools/test_unified_cli.py tests/tools/test_phase5_tooling.py tests/tools/test_tools_hardening.py` | CLI boundary, registry contract, hardening and compatibility behavior. | `conceptual` |

## Reference Docs

- [Validation README](./validation/README.md)
- [Workspace DevX README](./devx/workspace/README.md)
- [Architecture DevX README](./devx/architecture/README.md)
- [Connectors DevX README](./devx/connectors/README.md)
- [Foundry DevX README](./devx/foundry/README.md)
- [Ops README](../ops/README.md)
- [Tool Reference](../docs/reference/tools.md)
- [CI/CD Platform How-To](../docs/how-to/operate-ci-cd-platform.md)

## Current State

- `tools/<category>` остаются compatibility anchors; новый код должен жить
  только под zoned paths.
- `tools.registry` — source of truth для aliases, lifecycle status,
  dependency edges и docs generation.
- `workspace ci-parity` остаётся основным локальным umbrella-check для tools
  и docs surfaces.
- Last updated: 2026-04-17
