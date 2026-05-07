# Generated Index: Foundry Methods

Owner: `team-foundry`
Last updated: 2026-05-05

## Subtrees

| Path | Role |
| --- | --- |
| `artifacts/` | Method artifact contracts and fingerprints. |
| `backends/` | Runtime/backend adapters and checkpointing. |
| `bayesian/` | Flat Bayesian family facade over `catalog/bayesian/`. |
| `catalog/` | Builtin method families and registration roots. |
| `causal/` | Flat causal family facade over `catalog/causal/`. |
| `cli/` | Local scaffold and validation commands. |
| `compiler/` | Method compiler and hot-reload support. |
| `components/` | Component metadata and extension registration. |
| `econometrics/` | Flat econometrics family facade over `catalog/econometrics/`. |
| `lifecycle/` | Monitoring, compatibility, and output lifecycle helpers. |
| `selection/` | Method advisor and selection scoring. |
| `testing/` | Package-local testing helpers only. |
| `_internal/` | Private helpers with no public import contract. |

## Key Entrypoints

`__init__.py` and `api.py` own the package facade. Root compatibility modules
such as `registry.py`, `composer.py`, `linker.py`, `discovery.py`,
`catalog_snapshot.py`, and `deprecation.py` forward to the documented
subpackages and carry shim metadata where the import is public.
