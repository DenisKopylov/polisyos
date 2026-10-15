# Trinity (`polisyos.ir.trinity`)

## Purpose

`polisyos.ir.trinity` defines the canonical policy payload
`ProblemFrame + PolicySpec + ModelSpec`. It is the authoring and ingestion boundary
from which loader, linker, migration, and downstream compilation flows begin.

## Where to Start

- [`__init__.py`](./__init__.py) — `TrinityBundle` and the current bundle schema version.
- [`loaders.py`](./loaders.py) — strict loaders for `ProblemFrame`, `PolicySpec`, `ModelSpec`, and the complete bundle.
- [`../governance/problem_frame.py`](../governance/problem_frame.py) — the `Why` contract for problem framing.
- [`../governance/policy_spec.py`](../governance/policy_spec.py) — the `What` contract for interventions and execution semantics.
- [`../model_spec.py`](../model_layer/model_spec.py) — the `How` contract for the model and its assumptions.
- After authoring, see [`../linker/README.md`](../linker/README.md); for compatibility paths, see [`../migrations/README.md`](../migrations/README.md).

## Public entrypoints

| Entrypoint                                          | Use when                                              | Defined in                     |
| --------------------------------------------------- | ----------------------------------------------------- | ------------------------------ |
| `polisyos.ir.trinity.TrinityBundle`                 | Use the canonical container for the policy payload    | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.ProblemFrame`                  | Use the `Why` layer of Trinity                        | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.PolicySpec`                    | Use the `What` layer of Trinity                       | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.ModelSpec`                     | Use the `How` layer of Trinity                        | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.TRINITY_BUNDLE_SCHEMA_VERSION` | Identify the supported bundle version                 | [`__init__.py`](./__init__.py) |
| `polisyos.ir.trinity.loaders.load_problem_frame()`  | Load a `ProblemFrame` strictly                        | [`loaders.py`](./loaders.py)   |
| `polisyos.ir.trinity.loaders.load_policy_spec()`    | Load a `PolicySpec` strictly                          | [`loaders.py`](./loaders.py)   |
| `polisyos.ir.trinity.loaders.load_model_spec()`     | Load a `ModelSpec` strictly                           | [`loaders.py`](./loaders.py)   |
| `polisyos.ir.trinity.loaders.load_trinity_bundle()` | Load and validate a complete Trinity payload          | [`loaders.py`](./loaders.py)   |

## Depends on / depended on by

- Depends on: [`../governance/README.md`](../governance/README.md), [`../model_spec.py`](../model_layer/model_spec.py), `polisyos.ir.kernel.base`.
- Depended on by: `polisyos.ir.loading.loaders`, `polisyos.ir.migrations`, `polisyos.ir.linker`, `polisyos.foundry.compile`, `polisyos.scientist.agent`, `polisyos.lex`.

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
uv run pytest tests/unit/ir/test_trinity_loaders.py tests/contract/test_trinity_contracts.py tests/contract/test_trinity_linker_contract.py tests/contract/test_trinity_migration.py -q
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
