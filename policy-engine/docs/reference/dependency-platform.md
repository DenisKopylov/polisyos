# Dependency Platform

Owner: `@tools-owners`  
Backup owner: `@platform-owners`  
Source of truth: `pyproject.toml`, `tools/devx/workspace/_common.py`, `tools/devx/workspace/bootstrap.py`, `.github/actions/setup-policy-engine-python/action.yml`

Related guides: [Installation](../how-to/install.md), [Environment Matrix](environment-matrix.md), [Configuration Profiles](configuration-profiles.md).

This page is the source of truth for dependency tiers, curated extras, and the
rules for deciding where a new dependency should live.

Workspace toolchain baseline:

- Python `3.14.x`
- Node `22.x`
- `uv 0.9.21`

## Contributor Tiers

| Tier                               | Canonical command                                                             | Intended scope                                                                             |
| ---------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Minimal contributor                | `uv sync --frozen --extra lint --extra test`                                  | Core Python changes, linting, unit/property tests, no docs/frontend toolchain              |
| Docs contributor                   | `uv sync --frozen --extra lint --extra docs`                                  | MkDocs, docstring quality, docs accuracy and nav work                                      |
| Runtime contributor                | `uv sync --frozen --extra lint --extra test --extra runtime`                  | Runtime API, contracts, observability, backend contributors using the canonical local gate |
| Full research / causal contributor | `uv sync --frozen --extra lint --extra test --extra runtime --extra research` | Foundry, Scientist, causal, econometrics, and research-heavy flows                         |
| Frontend contributor               | `uv run polisyos-tools workspace bootstrap --profile runtime`                 | Runtime contributor Python surface plus `npm ci` and optional Playwright browser install   |

Repo-local workspace helpers encode the same tiers:

- `uv run polisyos-tools workspace bootstrap --profile minimal`
- `uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend`
- `uv run polisyos-tools workspace bootstrap --profile runtime`
- `uv run polisyos-tools workspace bootstrap --profile research`
- GitHub Actions should use the same profile names through `.github/actions/setup-policy-engine-python`.

## Tooling Dependency Rules

The tools platform uses the same dependency tiers as contributors:

- command metadata and the unified CLI must import under the minimal/runtime
  contributor path;

- docs validation may rely on the `docs` extra and is pulled by
  `polisyos-tools workspace ci-parity` only when docs checks are enabled;

- optional command families should declare missing imports or host executables
  through registry/preflight metadata instead of failing after partial work;

- cloud, benchmark, and release tools should document external prerequisites
  in their nearest README and keep Python wheels out of base install unless
  they are needed by the stable package import surface.

## Curated Extras

The Python extras are intentionally split into three kinds of surfaces:

| Extra                                                                                                     | Role                                                             |
| --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `lint`, `docs`, `notebooks`, `mutation`                                                                   | contributor-only tooling groups                                  |
| `runtime`, `research`, `all`                                                                              | curated umbrella installs for predictable onboarding and CI      |
| `analytics`, `ml`, `bayesian`, `causal-*`, `rag*`, `security`, `multi-tenant`, `agent-sim`, `apple-metal` | capability extras added only when that feature surface is needed |

Important umbrella intent:

- `runtime` is the backend contributor umbrella: Runtime HTTP, observability glue, structured logging.
- `research` is the full causal/research umbrella: econometrics, Bayesian, solvers, discovery, and academic helpers.
- `all` is a curated product-capability umbrella, not a contributor meta-extra. It deliberately excludes local-only tooling and the most platform-sensitive paths.

## Placement Policy

Use the following rules when adding or moving a dependency:

| Placement                    | Put a dependency here when...                                                                                                                                  | Examples                                                                                         |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Base install                 | Importing the published `polisyos` package would fail or lose core functionality without it; the dependency is portable enough for every supported environment | `jax`, `duckdb`, `pydantic`, `aiohttp`                                                           |
| Optional extra               | The dependency unlocks a bounded capability or a heavyweight workflow that not every contributor needs                                                         | `lightgbm`, `onnxruntime`, `boto3`, `presidio-*`, `plotly`                                       |
| Dev-only extra               | The dependency exists only for authoring, validation, docs, testing, notebooks, or local automation                                                            | `ruff`, `mypy`, `mkdocs`, `pytest-benchmark`, `mutmut`                                           |
| External system prerequisite | The feature depends more on host/runtime provisioning than on a Python wheel; the repo should document it but not silently install it everywhere               | PostgreSQL, Docker / dev containers, CUDA drivers, system OpenMP, Playwright browser OS packages |

Guardrails:

- Prefer base install only for dependencies needed by the stable import surface.
- Prefer an optional extra when the package is platform-sensitive, large, slow to compile, or tied to a specific feature family.
- Prefer a dev-only extra when the package never ships in runtime or research artifacts.
- Prefer an external prerequisite when success depends on host capabilities or credentials more than on `pip` resolution.

## Compatibility Notes

| Surface            | Notes                                                                                                                               |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `apple-metal`      | Opt-in only. Apple Metal is best-effort and should not be pulled into every macOS install by default.                               |
| `causal-core`      | `econml` is currently gated away from Python 3.14 in the verified contributor matrix.                                               |
| `causal-dowhy`     | `dowhy` 0.13 depends on an older `cvxpy` path; it stays isolated behind a compatibility extra.                                      |
| `causal-bcf`       | `stochtree` often needs OpenMP and host tuning, especially on macOS.                                                                |
| `rag-local`        | Local embedding stacks pull native runtimes such as `onnxruntime`; keep them opt-in.                                                |
| `table-extraction` | PDF extraction stacks can be heavyweight and may require host OCR/rendering tooling depending on workload.                          |
| `security`         | Security and privacy packages are intentionally opt-in so local onboarding does not silently drag in large NLP or cloud SDK stacks. |
| `multi-tenant`     | Requires a real PostgreSQL surface in practice; Python dependencies alone are not the whole story.                                  |
| `agent-sim`        | Visualization helpers (`plotly`, `streamlit`) are optional and do not belong in the base runtime path.                              |

## Resolver Hygiene Rules

- Reuse umbrella extras by reference instead of copying the same dependency list into multiple extras.
- Keep compatibility extras narrow and name them explicitly when they exist to isolate upstream conflicts.
- Avoid creating milestone or one-off umbrella extras unless they expose a stable workflow tier.
- Do not place platform-specific backends in the base install when a CPU-safe path already exists.
