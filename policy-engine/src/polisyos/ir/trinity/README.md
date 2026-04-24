# Trinity (`polisyos.ir.trinity`)

## Purpose

`polisyos.ir.trinity` определяет канонический policy payload
`ProblemFrame + PolicySpec + ModelSpec`. Это авторинговая и ingestion boundary,
с которой стартуют loader, linker, migration и downstream compile flows.

## Where to Start

- [`__init__.py`](./__init__.py) — `TrinityBundle` и текущая bundle schema version.
- [`loaders.py`](./loaders.py) — strict loaders для `ProblemFrame`, `PolicySpec`, `ModelSpec` и полного bundle.
- [`../governance/problem_frame.py`](../governance/problem_frame.py) — `Why`-контракт постановки задачи.
- [`../governance/policy_spec.py`](../governance/policy_spec.py) — `What`-контракт интервенций и execution semantics.
- [`../model_spec.py`](../model_spec.py) — `How`-контракт модели и assumptions.
- После authoring откройте [`../linker/README.md`](../linker/README.md), для compatibility-path'ов — [`../migrations/README.md`](../migrations/README.md).

## Public entrypoints

| Entrypoint                                          | Use when                                              | Defined in                     |
| --------------------------------------------------- | ----------------------------------------------------- | ------------------------------ |
| `polisyos.ir.trinity.TrinityBundle`                 | Нужен канонический контейнер для policy payload       | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.ProblemFrame`                  | Нужен `Why`-слой Trinity                              | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.PolicySpec`                    | Нужен `What`-слой Trinity                             | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.ModelSpec`                     | Нужен `How`-слой Trinity                              | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.TRINITY_BUNDLE_SCHEMA_VERSION` | Нужно зафиксировать supported bundle version          | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.loaders.load_problem_frame()`  | Нужен strict loader для `ProblemFrame`                | [`loaders.py`](./loaders.py)   |
| `polisyos.ir.trinity.loaders.load_policy_spec()`    | Нужен strict loader для `PolicySpec`                  | [`loaders.py`](./loaders.py)   |
| `polisyos.ir.trinity.loaders.load_model_spec()`     | Нужен strict loader для `ModelSpec`                   | [`loaders.py`](./loaders.py)   |
| `polisyos.ir.trinity.loaders.load_trinity_bundle()` | Нужно загрузить и валидировать полный Trinity payload | [`loaders.py`](./loaders.py)   |

## Depends on / depended on by

- Depends on: [`../governance/README.md`](../governance/README.md), [`../model_spec.py`](../model_spec.py), `polisyos.ir.kernel.base`.
- Depended on by: `polisyos.ir.loaders`, `polisyos.ir.migrations`, `polisyos.ir.linker`, `polisyos.foundry.compile`, `polisyos.scientist.agent`, `polisyos.lex`.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-04-17`.

```bash
uv run python -c "import polisyos.ir.trinity as trinity; print(trinity.TRINITY_BUNDLE_SCHEMA_VERSION, trinity.TrinityBundle.__name__)"
```

## Test/verification commands

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run this targeted suite before landing
Trinity contract changes.

```bash
uv run pytest tests/ir/test_trinity_loaders.py tests/contract/test_trinity_contracts.py tests/contract/test_trinity_linker_contract.py tests/contract/test_trinity_migration.py -q
```

## Reference docs

- [IR reference index](../../../../docs/reference/ir/index.md)
- [IR problem framing](../../../../docs/reference/ir/problem-framing.md)
- [IR governance reference](../../../../docs/reference/ir/governance.md)
- [TRINITY contract](../../../../docs/contracts/TRINITY.md)
- [Trinity explanation](../../../../docs/explanation/trinity.md)
- [IR root README](../README.md)
- [Linker README](../linker/README.md)
- [Migrations README](../migrations/README.md)

## Last updated

`2026-04-17`
