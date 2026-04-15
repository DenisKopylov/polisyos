# PolisyOS Workspace

Этот корень репозитория является workspace gateway. Канонический product root для
PolisyOS находится в [`policy-engine/`](./policy-engine/).

Если вам нужно понять, где начинается продукт, ориентир простой:

1. Перейдите в [`policy-engine/`](./policy-engine/).
2. Откройте [`policy-engine/README.md`](./policy-engine/README.md).
3. Для contributor setup используйте `python3 -m tools.cli workspace bootstrap`,
   `python3 -m tools.cli workspace doctor`,
   `python3 -m tools.cli workspace verify` из `policy-engine/`.

## Canonical Product Root

- Источник правды по продукту: [`policy-engine/`](./policy-engine/)
- Источник правды по продуктовой документации: [`policy-engine/docs/`](./policy-engine/docs/)
- Источник правды по packaging и lockfiles:
  [`policy-engine/pyproject.toml`](./policy-engine/pyproject.toml),
  [`policy-engine/uv.lock`](./policy-engine/uv.lock),
  [`policy-engine/frontend/runtime-dashboard/package-lock.json`](./policy-engine/frontend/runtime-dashboard/package-lock.json)
- Источник правды по release/runtime logic: код и automation внутри `policy-engine/`

Архитектурное решение зафиксировано в
[`ADR-0096`](./policy-engine/docs/adr/0096-canonical-product-root-and-workspace-boundary.md).

## Repository Topology

| Path | Role |
| --- | --- |
| [`policy-engine/`](./policy-engine/) | Канонический product root: код, docs, packaging, release/runtime logic |
| [`.github/`](./.github/) | Repo control plane для GitHub и platform-level automation |
| [`design/`](./design/) | Дизайн-артефакты и explorations, не являющиеся product source of truth |
| [`data/`](./data/) | Локальные datasets и snapshots, исключённые из product automation как canonical inputs |
| [`.cursor/`](./.cursor/), [`.claude/`](./.claude/), [`lefthook.yml`](./lefthook.yml) | Workspace-only helper files |

## Repo Control Plane

Некоторые файлы обязаны жить на уровне root не из архитектурных соображений, а по
требованиям GitHub и платформы:

- [`.github/workflows/`](./.github/workflows/) для GitHub Actions;
- root-level governance/config files вроде issue templates, `CODEOWNERS`,
  Dependabot-конфигурации и аналогичных repo-native GitHub файлов;
- этот `README.md` как входная точка в workspace;
- вспомогательные workspace-конфиги, которые GitHub, Codex и IDE ожидают в root.

Это считается repo control plane, а не product topology.

## Root-Level Policy

На уровне repository root могут жить только:

- research materials;
- local datasets, исключённые из product automation;
- design artifacts;
- workspace-only helper files;
- repo-native GitHub governance files.

На уровне repository root не должны появляться:

- product code;
- product docs как canonical source of truth;
- packaging metadata или lockfiles продукта;
- release logic продукта.

## What Must Live Under `policy-engine/`

Под `policy-engine/` обязательно живут:

- product code;
- product docs;
- packaging and lockfiles;
- release logic.

## Where To Go Next

- Product overview: [`policy-engine/README.md`](./policy-engine/README.md)
- Contributor guide: [`policy-engine/CONTRIBUTING.md`](./policy-engine/CONTRIBUTING.md)
- Architecture/docs site source: [`policy-engine/docs/`](./policy-engine/docs/)
