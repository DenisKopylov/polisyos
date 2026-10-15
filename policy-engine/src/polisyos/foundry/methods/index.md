# Generated Index: Foundry Methods

Owner: `team-foundry`
Last updated: 2026-10-14

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

`__init__.py` and `api.py` own the package facade. The root compatibility
facades `registry.py`, `composer.py`, and `deprecation.py` forward to their
documented subpackages. `discovery.py` is a package-level discovery module.
The linker implementation is at `components/linker.py`, and the catalog
snapshot implementation is at `catalog/snapshot.py`; neither has a root-level
`linker.py` or `catalog_snapshot.py` at this source snapshot.
